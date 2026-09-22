"""
Thin wrapper around the Google Gemini API (google-genai SDK).

Reads GEMINI_API_KEY from the environment (or from st.session_state, set via
the sidebar in app.py). Uses JSON mode so responses can be parsed reliably
into the schemas used by core/analysis.py.
"""
import os
import json
from google import genai
from google.genai import types

DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

_client = None


def get_client(api_key: str = None):
    global _client
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "No Gemini API key found. Set GEMINI_API_KEY as an environment "
            "variable, or paste it into the sidebar in the app."
        )
    # Rebuild the client if the key changed (e.g. pasted into the sidebar)
    if _client is None or getattr(_client, "_case_key", None) != key:
        _client = genai.Client(api_key=key)
        _client._case_key = key
    return _client


def call_json(system_prompt: str, user_prompt: str, api_key: str = None,
               model: str = None, temperature: float = 0) -> dict:
    """Call the model and parse a JSON object response. Raises on bad JSON
    rather than silently guessing, so failures are visible instead of
    producing a plausible-looking but wrong answer."""
    client = get_client(api_key)
    resp = client.models.generate_content(
        model=model or DEFAULT_MODEL,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )
    content = resp.text
    print(content)
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError) as e:
        raise RuntimeError(f"Model did not return valid JSON: {e}\nRaw output:\n{content}")
