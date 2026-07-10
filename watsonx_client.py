"""
WatsonX API client — wraps the IBM watsonx.ai chat REST endpoint.
All agents use this single client for consistency.
"""

import time
import threading
import requests
import config

# ── IAM token cache (avoids a round-trip on every request) ──────────────────
_token_cache: dict = {"token": "", "expires_at": 0.0}
_token_lock = threading.Lock()


def _get_iam_token() -> str:
    """
    Exchange the API key for a short-lived IAM bearer token.
    Caches the token and only refreshes when it's within 60 s of expiry.
    """
    with _token_lock:
        if time.time() < _token_cache["expires_at"] - 60:
            return _token_cache["token"]

        resp = requests.post(
            "https://iam.cloud.ibm.com/identity/token",
            data={
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": config.WATSONX_API_KEY,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        _token_cache["token"]      = data["access_token"]
        _token_cache["expires_at"] = time.time() + int(data.get("expires_in", 3600))
        return _token_cache["token"]


def chat(
    messages: list[dict],
    system_prompt: str = "",
    max_tokens: int = config.DEFAULT_MAX_TOKENS,
    temperature: float = config.DEFAULT_TEMPERATURE,
) -> str:
    """
    Send a chat request to IBM WatsonX granite model.

    Args:
        messages:      List of {"role": "user"|"assistant", "content": "..."}.
        system_prompt: Optional system message prepended to the conversation.
        max_tokens:    Maximum tokens to generate.
        temperature:   Sampling temperature (lower = more deterministic).

    Returns:
        The assistant reply as a plain string.
    """
    token = _get_iam_token()

    all_messages = []
    if system_prompt:
        all_messages.append({"role": "system", "content": system_prompt})
    all_messages.extend(messages)

    payload = {
        "model_id": config.WATSONX_MODEL_ID,
        "project_id": config.WATSONX_PROJECT_ID,
        "messages": all_messages,
        "parameters": {
            "max_new_tokens": max_tokens,
            "temperature": temperature,
        },
    }

    resp = requests.post(
        config.CHAT_ENDPOINT,
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()

    # Extract the assistant message content
    return data["choices"][0]["message"]["content"]
