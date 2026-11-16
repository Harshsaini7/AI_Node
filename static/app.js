"use strict";

const POLL_MS = 1000;

const els = {
  start: document.getElementById("start-btn"),
  stop: document.getElementById("stop-btn"),
  status: document.getElementById("status"),
  customer: document.getElementById("customer"),
  pending: document.getElementById("pending"),
  message: document.getElementById("message"),
  transcript: document.getElementById("transcript"),
  form: document.getElementById("reply-form"),
  input: document.getElementById("reply-input"),
  send: document.getElementById("reply-btn"),
  mic: document.getElementById("mic-btn"),
  speak: document.getElementById("speak-toggle"),
  auto: document.getElementById("auto-toggle"),
  summary: document.getElementById("summary"),
};

const AUDIO_TYPES = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/webm", "audio/mp4"];
const MAX_RECORD_MS = 30000; // keeps the upload far below the server's 2 MB limit
// Hands-free mode: stop recording after silence, give up if nobody speaks.
const VAD = { threshold: 0.015, silenceMs: 1500, noSpeechMs: 10000, tickMs: 100 };

let lastTranscriptKey = "";
let recorder = null; // active MediaRecorder, or null
let recordTimer = null;
let transcribing = false;
let lastServerMessage = null;
let lastAwaiting = false; // latest awaiting_reply from the server
let starting = false; // a recording is being set up (waiting for the mic permission)
let autoPaused = false; // hands-free gave up for this question; the MIC button still works
let vadTimer = null;
let audioCtx = null;
let speechCount = 0; // utterances queued or playing
let seenLines = null; // number of transcript lines already handled (null until the first poll)
let startEpoch = 0; // bumped on START so stale in-flight status polls are ignored

const TTS_LANG = "en-IN";
const ttsSupported = "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
if (!ttsSupported) {
  els.speak.disabled = true;
  els.speak.checked = false;
  els.speak.parentElement.title = "Spoken replies are not supported in this browser.";
}

// True while the agent's voice is queued or playing. The mic stays closed then,
// so the microphone cannot pick up the agent's own voice.
function isSpeaking() {
  if (!ttsSupported || speechCount <= 0) {
    return false;
  }
  const synth = window.speechSynthesis;
  return synth.speaking || synth.pending;
}

function speechFinished() {
  speechCount = Math.max(0, speechCount - 1);
  if (speechCount === 0) {
    updateMic(lastAwaiting);
    maybeAutoListen(lastAwaiting);
  }
}

function speak(text) {
  if (!ttsSupported || !els.speak.checked) {
    return;
  }
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = TTS_LANG;
  utterance.onend = speechFinished;
  utterance.onerror = speechFinished;
  speechCount += 1;
  window.speechSynthesis.speak(utterance); // queued: lines are spoken in order
}

function stopSpeaking() {
  if (ttsSupported) {
    speechCount = 0;
    window.speechSynthesis.cancel();
  }
}

// Speak only the agent lines that are new since the last poll.
function speakNewLines(lines) {
  if (seenLines === null) {
    seenLines = lines.length; // first poll: do not read old history aloud
  } else if (lines.length < seenLines) {
    seenLines = 0; // a new run reset the transcript
  }
  for (const line of lines.slice(seenLines)) {
    if (line.role === "agent") {
      autoPaused = false; // a new question: hands-free may listen again
      speak(line.text);
    }
  }
  seenLines = lines.length;
}

els.speak.addEventListener("change", () => {
  if (!els.speak.checked) {
    stopSpeaking();
    updateMic(lastAwaiting);
    maybeAutoListen(lastAwaiting);
  }
});

els.auto.addEventListener("change", () => {
  autoPaused = false;
  if (els.auto.checked) {
    maybeAutoListen(lastAwaiting);
  } else if (recorder) {
    stopRecording(false); // hands-free was switched off: drop the recording
  }
});

function showMessage(text) {
  els.message.textContent = text || "";
  els.message.hidden = !text;
}

async function post(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  let data = {};
  try {
    data = await response.json();
  } catch (_ignored) {
    /* keep empty data */
  }
  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }
  return data;
}

function renderTranscript(lines) {
  const key = JSON.stringify(lines);
  if (key === lastTranscriptKey) {
    return;
  }
  lastTranscriptKey = key;

  els.transcript.replaceChildren();
  if (lines.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "Press START AGENT to begin.";
    els.transcript.appendChild(empty);
    return;
  }
  for (const line of lines) {
    const p = document.createElement("p");
    const role = ["agent", "customer", "system"].includes(line.role) ? line.role : "system";
    p.className = role;
    p.textContent = line.text; // textContent: never interpret AI/customer text as HTML
    els.transcript.appendChild(p);
  }
  els.transcript.scrollTop = els.transcript.scrollHeight;
}

function render(state) {
  els.status.textContent = state.status;
  els.status.className = "badge " + state.status.toLowerCase().replace(/[^a-z]/g, "");
  els.customer.textContent = state.current_customer || "-";
  els.pending.textContent = state.pending_count === null ? "-" : String(state.pending_count);
  if (state.message !== lastServerMessage) { // do not wipe local messages (e.g. mic errors) on every poll
    lastServerMessage = state.message;
    showMessage(state.message);
  }

  els.start.disabled = state.is_running;
  els.stop.disabled = !state.is_running || state.status === "STOPPING";
  els.input.disabled = !state.awaiting_reply;
  els.send.disabled = !state.awaiting_reply;
  if (!state.awaiting_reply && recorder) {
    stopRecording(false); // the question is gone (Stop pressed or timeout): drop the audio
  }
  lastAwaiting = state.awaiting_reply;
  if (state.awaiting_reply && document.activeElement !== els.input) {
    els.input.focus();
  }

  renderTranscript(state.transcript);
  if (!state.is_running) {
    stopSpeaking(); // a stopped or finished run must not keep talking
  }
  speakNewLines(state.transcript);
  updateMic(state.awaiting_reply);
  maybeAutoListen(state.awaiting_reply);

  const s = state.summary;
  els.summary.textContent =
    "Interested: " + s.interested + "  |  Not interested: " + s.not_interested +
    "  |  Skipped: " + s.skipped + "  |  Needs retry: " + s.errors;
}

function updateMic(awaiting) {
  const supported = Boolean(navigator.mediaDevices && window.MediaRecorder);
  els.mic.disabled = !supported || transcribing || starting || isSpeaking() || !(awaiting || recorder);
  els.mic.classList.toggle("recording", Boolean(recorder));
  els.mic.textContent = recorder ? "STOP" : transcribing ? "..." : "MIC";
  if (!supported) {
    els.mic.title = "Voice input is not supported in this browser. Please type.";
  }
}

function stopVad() {
  clearInterval(vadTimer);
  vadTimer = null;
  if (audioCtx) {
    audioCtx.close();
    audioCtx = null;
  }
}

// Hands-free: watch the mic level. Stop and send after silence that follows speech;
// give up (and wait for the MIC button) if nobody speaks at all.
function startVad(stream) {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) {
    return;
  }
  audioCtx = new AudioContextClass();
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 1024;
  audioCtx.createMediaStreamSource(stream).connect(analyser);
  const samples = new Float32Array(analyser.fftSize);
  const began = performance.now();
  let lastVoice = began;
  let heard = false;

  vadTimer = setInterval(() => {
    analyser.getFloatTimeDomainData(samples);
    let sum = 0;
    for (const value of samples) {
      sum += value * value;
    }
    const now = performance.now();
    if (Math.sqrt(sum / samples.length) > VAD.threshold) {
      heard = true;
      lastVoice = now;
    }
    if (heard && now - lastVoice > VAD.silenceMs) {
      stopRecording(true);
    } else if (!heard && now - began > VAD.noSpeechMs) {
      autoPaused = true;
      showMessage("I could not hear you. Click MIC to talk, or type the reply.");
      stopRecording(false);
    }
  }, VAD.tickMs);
}

function stopRecording(send) {
  if (!recorder || recorder.state === "inactive") {
    return;
  }
  stopVad();
  recorder.sendAfterStop = send;
  clearTimeout(recordTimer);
  recorder.stop(); // the "stop" handler does the rest
}

// Hands-free mode: open the mic when a reply is awaited and the agent is silent.
function maybeAutoListen(awaiting) {
  if (els.auto.checked && awaiting && !autoPaused && !recorder && !starting && !transcribing && !isSpeaking()) {
    startRecording(true);
  }
}

async function startRecording(auto) {
  if (starting || recorder) {
    return;
  }
  starting = true;
  updateMic(lastAwaiting);
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    });
  } catch (_error) {
    autoPaused = true; // never retry in a loop
    showMessage("Microphone access was blocked. Allow it in the browser's address bar, or type the reply.");
    return;
  } finally {
    starting = false;
  }
  if (!lastAwaiting || isSpeaking()) {
    stream.getTracks().forEach((track) => track.stop()); // the question went away while asking for the mic
    updateMic(lastAwaiting);
    return;
  }

  const mimeType = AUDIO_TYPES.find((type) => MediaRecorder.isTypeSupported(type));
  const chunks = [];
  const rec = mimeType ? new MediaRecorder(stream, { mimeType: mimeType }) : new MediaRecorder(stream);
  rec.sendAfterStop = false;
  rec.addEventListener("dataavailable", (event) => {
    if (event.data.size > 0) {
      chunks.push(event.data);
    }
  });
  rec.addEventListener("stop", async () => {
    stopVad();
    stream.getTracks().forEach((track) => track.stop()); // release the microphone
    recorder = null;
    if (!rec.sendAfterStop || chunks.length === 0) {
      updateMic(false);
      return;
    }
    await sendAudio(new Blob(chunks, { type: rec.mimeType || mimeType || "audio/webm" }));
  });

  recorder = rec;
  showMessage("");
  rec.start();
  recordTimer = setTimeout(() => stopRecording(true), MAX_RECORD_MS);
  if (auto) {
    startVad(stream);
  }
  updateMic(true);
}

async function sendAudio(blob) {
  transcribing = true;
  updateMic(true);
  showMessage("Transcribing...");
  try {
    const response = await fetch("/api/transcribe", {
      method: "POST",
      headers: { "Content-Type": blob.type },
      body: blob,
    });
    let data = {};
    try {
      data = await response.json();
    } catch (_ignored) {
      /* keep empty data */
    }
    if (!response.ok) {
      throw new Error(data.error || "Could not process the audio.");
    }
    showMessage(data.text ? "" : "I could not hear any speech. Please try again or type the reply.");
  } catch (error) {
    showMessage(error.message);
  } finally {
    transcribing = false;
    refresh();
  }
}

els.mic.addEventListener("click", () => {
  if (recorder) {
    stopRecording(true);
  } else if (!transcribing) {
    startRecording();
  }
});

async function refresh() {
  const epoch = startEpoch;
  try {
    const response = await fetch("/api/status");
    if (!response.ok) {
      throw new Error("status failed");
    }
    const state = await response.json();
    if (epoch === startEpoch) { // ignore a poll that began before START was clicked
      render(state);
    }
  } catch (_error) {
    showMessage("Cannot reach the server. Is it still running?");
  }
}

els.start.addEventListener("click", async () => {
  els.start.disabled = true;
  try {
    await post("/api/start");
    startEpoch += 1; // drop polls that started before the server reset its transcript
    seenLines = 0; // speak the new run from its first line
    showMessage("");
  } catch (error) {
    showMessage(error.message);
  }
  refresh();
});

els.stop.addEventListener("click", async () => {
  els.stop.disabled = true;
  try {
    await post("/api/stop");
  } catch (error) {
    showMessage(error.message);
  }
  refresh();
});

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = els.input.value.trim();
  if (!text) {
    return;
  }
  els.send.disabled = true;
  try {
    await post("/api/reply", { text: text });
    els.input.value = "";
    showMessage("");
  } catch (error) {
    showMessage(error.message);
  }
  refresh();
});

refresh();
setInterval(refresh, POLL_MS);
