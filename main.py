"""
AI Loan Customer Agent - Web UI
===============================
A simple Flask page with START / STOP buttons, the agent status,
the current customer and a chat box for the customer's reply.

Run:
    python main.py
Then open http://127.0.0.1:5000

Security notes:
- The server only listens on 127.0.0.1 (never on all interfaces).
- Requests must use a localhost Host header (blocks DNS rebinding).
- POST requests must be JSON (except /api/transcribe, which takes recorded audio) and,
  if they carry an Origin, it must be localhost (blocks other websites from controlling the agent).
- Error responses are generic; details go to the server log only.

Phase 2.4 - Flask Web UI
Phase 4.1 - Speech-to-Text (POST /api/transcribe)
"""

from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

# Load environment variables from .env file (before importing modules that read them)
load_dotenv()

from agent import Agent  # noqa: E402
from logger import log  # noqa: E402
from stt_provider import SttError, transcribe  # noqa: E402

# Path to the spreadsheet
SPREADSHEET_PATH = "loan_leads.xlsx"

# Server binding: localhost only
HOST = "127.0.0.1"
PORT = 5000
ALLOWED_HOSTNAMES = {"127.0.0.1", "localhost"}

# Recorded audio is bigger than a typed reply, so /api/transcribe has its own limit
AUDIO_MAX_BYTES = 2 * 1024 * 1024
AUDIO_TYPES = {"audio/webm", "audio/ogg", "audio/mp4", "audio/wav", "audio/x-wav"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024  # replies are tiny; reject big bodies

agent = Agent(SPREADSHEET_PATH)


def _hostname(value):
    """Hostname part of a Host header or Origin URL, or None if it cannot be parsed."""
    try:
        if "//" not in value:
            value = "//" + value
        return urlsplit(value).hostname
    except ValueError:
        return None


@app.before_request
def guard_requests():
    """Reject requests that did not come from this machine's own pages."""
    if _hostname(request.host) not in ALLOWED_HOSTNAMES:
        return jsonify({"error": "Forbidden"}), 403

    if request.method == "POST":
        origin = request.headers.get("Origin")
        if origin and _hostname(origin) not in ALLOWED_HOSTNAMES:
            return jsonify({"error": "Forbidden"}), 403
        if request.path == "/api/transcribe":
            request.max_content_length = AUDIO_MAX_BYTES  # this route only
            if request.mimetype not in AUDIO_TYPES:
                return jsonify({"error": "Audio body required"}), 415
            if request.content_length and request.content_length > AUDIO_MAX_BYTES:
                return jsonify({"error": "Request too large"}), 413
        elif not request.is_json:
            return jsonify({"error": "JSON body required"}), 415

    return None


@app.after_request
def add_security_headers(response):
    """Basic hardening headers for every response."""
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(405)
def method_not_allowed(_error):
    return jsonify({"error": "Method not allowed"}), 405


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "Request too large"}), 413


@app.errorhandler(Exception)
def unexpected_error(error):
    """Never leak internals to the browser; log them server-side."""
    code = getattr(error, "code", None)
    if isinstance(code, int) and code < 500:
        return jsonify({"error": "Bad request"}), code
    log.error(f"Unhandled error: {error}", exc_info=True)
    return jsonify({"error": "Internal error"}), 500


@app.get("/")
def index():
    return render_template("index.html", spreadsheet=SPREADSHEET_PATH)


@app.get("/api/status")
def api_status():
    return jsonify(agent.get_status())


@app.post("/api/start")
def api_start():
    if not agent.start():
        return jsonify({"error": "The agent is already running."}), 409
    return jsonify({"ok": True})


@app.post("/api/stop")
def api_stop():
    if not agent.stop():
        return jsonify({"error": "The agent is not running."}), 409
    return jsonify({"ok": True})


@app.post("/api/reply")
def api_reply():
    data = request.get_json(silent=True)
    text = data.get("text") if isinstance(data, dict) else None
    ok, error = agent.submit_reply(text)
    if not ok:
        return jsonify({"error": error}), 400
    return jsonify({"ok": True})


@app.post("/api/transcribe")
def api_transcribe():
    """Turn recorded audio into text and give it to the agent as the customer's reply."""
    # Cheap check first so we do not spend CPU on audio nobody is waiting for.
    # submit_reply() checks again, so a reply that arrives meanwhile is still handled safely.
    if not agent.awaiting_reply:
        return jsonify({"error": "The agent is not waiting for a reply right now."}), 409

    audio = request.get_data()  # raises 413 if it exceeds AUDIO_MAX_BYTES
    if not audio:
        return jsonify({"error": "No audio received."}), 400

    try:
        text = transcribe(audio)
    except SttError:  # details were already logged
        return jsonify({"error": "Could not process the audio. Please try again or type."}), 422

    if not text:
        # Silence or noise: nothing is submitted, the question stays open
        return jsonify({"text": ""})

    ok, error = agent.submit_reply(text)
    if not ok:
        return jsonify({"error": error}), 409
    log.info(f"Voice reply accepted ({len(text)} characters).")  # never log the content
    return jsonify({"text": text})


if __name__ == "__main__":
    log.info(f"Open http://{HOST}:{PORT} in your browser. Press Ctrl+C to quit.")
    # debug=False: the Werkzeug debugger allows code execution and must never be on
    app.run(host=HOST, port=PORT, debug=False)
