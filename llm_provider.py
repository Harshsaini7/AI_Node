"""
LLM Provider
=============
Modular LLM integration layer.

Currently supports:
- Groq (hosted gpt-oss-120b, OpenAI-compatible API)
- Gemini (Google AI) - Free Tier
- Ollama (local models, no quota)

Choose with LLM_PROVIDER=groq|gemini|ollama in .env (see get_llm_provider()).

The rest of the application only interacts with the LLM through
this module, so switching providers requires no changes elsewhere.

Phase 3.1 - Gemini API Integration (Hello World)
"""

import json
import os
import urllib.error
import urllib.request

from google import genai
from logger import log

# Model used when GEMINI_MODEL is not set in .env.
# "flash-lite" models normally have the highest free-tier daily quota.
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"

# Groq defaults (HTTPS only)
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TIMEOUT_SECONDS = 60
GROQ_REASONING_EFFORT = "low"  # interest check needs no deep reasoning

# Ollama defaults (local server, never exposed to the network)
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
OLLAMA_TIMEOUT_SECONDS = 120  # first request can be slow while the model loads


class LLMFatalError(Exception):
    """Raised when the LLM cannot work at all (bad key, daily quota gone). Retrying is pointless."""


class QuotaExhaustedError(LLMFatalError):
    """Raised when the provider's DAILY quota is used up (retrying is pointless)."""


def _is_daily_quota_error(error_str):
    """True if a 429 error says the per-DAY quota is exhausted (not just per-minute)."""
    lowered = error_str.lower()
    return "perday" in lowered or "per day" in lowered or "daily" in lowered


class GeminiProvider:
    """
    LLM provider using Google's Gemini API.

    Usage:
        provider = GeminiProvider()
        response = provider.chat("Hello!")
        print(response)
    """

    def __init__(self, model_name=None):
        """
        Initialize the Gemini provider.

        Args:
            model_name (str): Gemini model to use. If None, uses the GEMINI_MODEL
                              environment variable, then DEFAULT_GEMINI_MODEL.
        """
        self.model_name = model_name or os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL

        # Get API key from environment
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not found in environment variables.\n"
                "1. Get a free key at: https://aistudio.google.com/apikey\n"
                "2. Add it to your .env file: GEMINI_API_KEY=your_key_here"
            )

        # Create the Gemini client
        self.client = genai.Client(api_key=api_key)
        log.info(f"Gemini provider initialized (model: {self.model_name})")

    def chat(self, message, system_instruction=None, json_mode=False):
        """
        Send a message to Gemini and get a response.

        Includes automatic retry for temporary server errors (503, 429).

        Args:
            message (str): The user message to send
            system_instruction (str): Optional system prompt to guide the AI's behavior
            json_mode (bool): If True, ask the model to reply with valid JSON only

        Returns:
            str: The AI's response text

        Raises:
            QuotaExhaustedError: If the daily free-tier quota is used up
            Exception: If the API call fails after all retries
        """
        import time as _time
        max_retries = 3
        # Build config with optional system instruction / JSON output
        config_args = {}
        if system_instruction:
            config_args["system_instruction"] = system_instruction
        if json_mode:
            config_args["response_mime_type"] = "application/json"
        config = genai.types.GenerateContentConfig(**config_args) if config_args else None

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=message,
                    config=config,
                )
                return response.text.strip()

            except Exception as e:
                last_error = e
                error_str = str(e)

                # Daily quota gone: retrying cannot succeed, so fail immediately
                if "429" in error_str and _is_daily_quota_error(error_str):
                    log.error("Gemini daily quota exhausted.")
                    raise QuotaExhaustedError(error_str) from e

                # Retry on temporary server errors (503 overload, 429 rate limit)
                is_retryable = "503" in error_str or "429" in error_str or "UNAVAILABLE" in error_str
                if is_retryable and attempt < max_retries:
                    wait_time = 2 ** (attempt + 1)  # 2s, 4s, 8s
                    log.warning(f"Gemini temporarily unavailable. Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    _time.sleep(wait_time)
                else:
                    log.error(f"Gemini API error: {e}")
                    raise


class OllamaProvider:
    """
    LLM provider using a local Ollama server. Free, offline, no daily quota.

    Setup:
        1. Install Ollama from https://ollama.com
        2. ollama pull llama3.2:3b
        3. Set LLM_PROVIDER=ollama in .env

    Usage:
        provider = OllamaProvider()
        print(provider.chat("Hello!"))
    """

    def __init__(self, model_name=None, host=None):
        """
        Args:
            model_name (str): Ollama model. If None, uses OLLAMA_MODEL env var,
                              then DEFAULT_OLLAMA_MODEL.
            host (str): Ollama server URL. If None, uses OLLAMA_HOST env var,
                        then DEFAULT_OLLAMA_HOST (localhost only by default).
        """
        self.model_name = model_name or os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL
        self.host = (host or os.getenv("OLLAMA_HOST") or DEFAULT_OLLAMA_HOST).rstrip("/")
        if not self.host.startswith(("http://", "https://")):
            raise ValueError("OLLAMA_HOST must start with http:// or https://")
        log.info(f"Ollama provider initialized (model: {self.model_name}, host: {self.host})")

    def chat(self, message, system_instruction=None, json_mode=False):
        """
        Send a message to the local Ollama model and get a response.

        Args:
            message (str): The user message to send
            system_instruction (str): Optional system prompt
            json_mode (bool): If True, force the model to reply with valid JSON

        Returns:
            str: The model's response text

        Raises:
            Exception: If Ollama is unreachable or returns an invalid response
        """
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": message})

        payload = {"model": self.model_name, "messages": messages, "stream": False}
        if json_mode:
            payload["format"] = "json"

        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
                data = json.loads(response.read().decode("utf-8"))
            return data["message"]["content"].strip()
        except urllib.error.URLError as e:
            log.error(
                f"Cannot reach Ollama at {self.host}. Is it installed and running? "
                f"Did you run 'ollama pull {self.model_name}'? ({e.reason})"
            )
            raise
        except (KeyError, ValueError) as e:
            log.error(f"Invalid response from Ollama: {e}")
            raise


class GroqProvider:
    """
    LLM provider using Groq's OpenAI-compatible API (default model: gpt-oss-120b).

    Setup:
        1. Create a key at https://console.groq.com/keys
        2. Add GROQ_API_KEY=... to .env
        3. Set LLM_PROVIDER=groq in .env
    """

    def __init__(self, model_name=None):
        """
        Args:
            model_name (str): Groq model ID. If None, uses GROQ_MODEL env var,
                              then DEFAULT_GROQ_MODEL.
        """
        self.model_name = model_name or os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL
        self._api_key = (os.getenv("GROQ_API_KEY") or "").strip()
        if not self._api_key:
            raise ValueError(
                "GROQ_API_KEY not found in environment variables.\n"
                "1. Create a key at: https://console.groq.com/keys\n"
                "2. Add it to your .env file: GROQ_API_KEY=your_key_here"
            )
        log.info(f"Groq provider initialized (model: {self.model_name})")

    def chat(self, message, system_instruction=None, json_mode=False):
        """
        Send a message to the Groq-hosted model and get a response.

        Retries temporary errors (429 per-minute limit, 5xx). A daily-limit 429
        raises QuotaExhaustedError immediately.

        Args:
            message (str): The user message to send
            system_instruction (str): Optional system prompt
            json_mode (bool): If True, force the model to reply with valid JSON

        Returns:
            str: The model's response text

        Raises:
            QuotaExhaustedError: If the daily quota is used up
            Exception: If the API call fails after all retries
        """
        import time as _time
        max_retries = 3

        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": message})

        payload = {
            "model": self.model_name,
            "messages": messages,
            "max_completion_tokens": 1024,  # reasoning tokens count towards this
        }
        if "gpt-oss" in self.model_name:
            payload["reasoning_effort"] = GROQ_REASONING_EFFORT
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        body = json.dumps(payload).encode("utf-8")

        for attempt in range(max_retries + 1):
            request = urllib.request.Request(
                GROQ_URL,
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                    "User-Agent": "ai-loan-agent/1.0",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=GROQ_TIMEOUT_SECONDS) as response:
                    data = json.loads(response.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()

            except urllib.error.HTTPError as e:
                error_text = e.read().decode("utf-8", errors="replace")[:500]

                if e.code in (401, 403):
                    log.error(f"Groq rejected the API key ({e.code}). Check GROQ_API_KEY in .env.")
                    raise LLMFatalError(f"Groq authentication failed ({e.code})") from e

                if e.code == 429 and _is_daily_quota_error(error_text):
                    log.error("Groq daily quota exhausted.")
                    raise QuotaExhaustedError(error_text) from e

                if (e.code == 429 or e.code >= 500) and attempt < max_retries:
                    try:
                        wait_time = min(float(e.headers.get("retry-after", "")), 30)
                    except ValueError:
                        wait_time = 2 ** (attempt + 1)  # 2s, 4s, 8s
                    log.warning(f"Groq temporarily unavailable ({e.code}). Retrying in {wait_time:.0f}s... "
                                f"(attempt {attempt + 1}/{max_retries})")
                    _time.sleep(wait_time)
                    continue

                log.error(f"Groq API error {e.code}: {error_text}")
                raise

            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < max_retries:
                    wait_time = 2 ** (attempt + 1)
                    log.warning(f"Groq network error. Retrying in {wait_time}s... "
                                f"(attempt {attempt + 1}/{max_retries})")
                    _time.sleep(wait_time)
                    continue
                log.error(f"Cannot reach Groq: {e}")
                raise

            except (KeyError, IndexError, ValueError) as e:
                log.error(f"Invalid response from Groq: {e}")
                raise


def get_llm_provider():
    """
    Create the LLM provider chosen by the LLM_PROVIDER environment variable.

    LLM_PROVIDER=groq, gemini (default) or ollama

    Raises:
        ValueError: If the provider name is unknown or its configuration is invalid
    """
    name = (os.getenv("LLM_PROVIDER") or "gemini").strip().lower()
    if name == "groq":
        return GroqProvider()
    if name == "gemini":
        return GeminiProvider()
    if name == "ollama":
        return OllamaProvider()
    raise ValueError(f"Unknown LLM_PROVIDER '{name}'. Use 'groq', 'gemini' or 'ollama'.")


# ---- Run this file directly to test ----
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    print("=" * 50)
    print("  GEMINI API - Hello World Test")
    print("=" * 50)
    print()

    # Test 1: Initialize provider
    try:
        provider = GeminiProvider()
        print("[OK] Gemini provider initialized")
    except ValueError as e:
        print(f"[ERROR] {e}")
        exit(1)

    # Test 2: Simple chat
    print()
    print("Sending: 'Say hello in one sentence.'")
    print("-" * 40)
    response = provider.chat("Say hello in one sentence.")
    print(f"Gemini: {response}")
    print()

    # Test 3: Chat with system instruction
    print("Sending with system prompt (bank agent)...")
    print("-" * 40)
    response = provider.chat(
        message="Who are you?",
        system_instruction="You are a polite customer success partner for a bank. Reply in 1-2 sentences."
    )
    print(f"Gemini: {response}")
    print()

    print("[OK] Phase 3.1 complete!")
