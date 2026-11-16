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
  summary: document.getElementById("summary"),
};

let lastTranscriptKey = "";

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
  showMessage(state.message);

  els.start.disabled = state.is_running;
  els.stop.disabled = !state.is_running || state.status === "STOPPING";
  els.input.disabled = !state.awaiting_reply;
  els.send.disabled = !state.awaiting_reply;
  if (state.awaiting_reply && document.activeElement !== els.input) {
    els.input.focus();
  }

  renderTranscript(state.transcript);

  const s = state.summary;
  els.summary.textContent =
    "Interested: " + s.interested + "  |  Not interested: " + s.not_interested +
    "  |  Skipped: " + s.skipped + "  |  Needs retry: " + s.errors;
}

async function refresh() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) {
      throw new Error("status failed");
    }
    render(await response.json());
  } catch (_error) {
    showMessage("Cannot reach the server. Is it still running?");
  }
}

els.start.addEventListener("click", async () => {
  els.start.disabled = true;
  try {
    await post("/api/start");
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
