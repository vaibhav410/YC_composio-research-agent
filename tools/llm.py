import json
import os
import re
import time

import requests
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
load_dotenv(".env.local")

DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_client = None
_fallback_model = None
_last_call = 0.0
_min_interval = 60.0 / 25


def _get_client():
    global _client
    if _client is None:
        key = os.getenv("GROQ_API_KEY") or os.getenv("Groq_api_key")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set")
        _client = Groq(api_key=key)
    return _client


def set_fallback(model):
    global _fallback_model
    _fallback_model = model


def _openrouter_key():
    key = os.getenv("OPENROUTER_API_KEY") or os.getenv("openrouter_api_key")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    return key


def _call_openrouter(model, system, user, max_tokens):
    resp = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {_openrouter_key()}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        },
        timeout=90,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"openrouter {resp.status_code}: {resp.text[:300]}")
    body = resp.json()
    if "choices" not in body or not body["choices"]:
        raise RuntimeError(f"openrouter bad response: {str(body)[:300]}")
    return body["choices"][0]["message"]["content"]


def _call_groq(model, system, user, max_tokens):
    resp = _get_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content


def provider_exhausted(error):
    text = str(error)
    return any(code in text for code in ("402", "429", "openrouter 404", "openrouter 401"))


def set_rpm(rpm):
    global _min_interval
    _min_interval = 60.0 / max(rpm, 1)


def _throttle():
    global _last_call
    wait = _min_interval - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()


def request_too_large(error):
    text = str(error)
    return (
        "Request too large" in text
        or "maximum context length" in text
        or "context_length_exceeded" in text
    )


def _dispatch(model, system, user, max_tokens):
    if model.startswith("openrouter/"):
        return _call_openrouter(model.removeprefix("openrouter/"), system, user, max_tokens)
    return _call_groq(model.split("/")[-1], system, user, max_tokens)


def complete(system, user, model=DEFAULT_MODEL, retries=4, max_tokens=1400):
    last_error = None
    for attempt in range(retries):
        _throttle()
        try:
            return _dispatch(model, system, user, max_tokens)
        except Exception as e:
            last_error = e
            if request_too_large(e):
                raise
            if attempt < retries - 1:
                time.sleep(10 * (attempt + 1) if "429" in str(e) else 3)
    if _fallback_model and _fallback_model != model:
        return complete(system, user, model=_fallback_model, retries=2, max_tokens=max_tokens)
    raise last_error


def complete_json(system, user, model=DEFAULT_MODEL, retries=3):
    for attempt in range(retries):
        raw = complete(system, user, model=model)
        parsed = extract_json(raw)
        if parsed is not None:
            return parsed
        user = user + "\n\nYour last reply was not valid JSON. Reply with a single JSON object only."
    raise ValueError("could not get valid JSON from model")


def extract_json(text):
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
