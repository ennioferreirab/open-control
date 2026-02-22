"""Anthropic OAuth — Authorization Code + PKCE flow.

Implements the full OAuth flow for Anthropic (claude.ai), allowing use of
Claude Pro/Max subscriptions without an API key. Tokens are stored in
~/.nanobot/anthropic_oauth.json with 0600 permissions.

NOTE: Anthropic's OAuth deviates from standard RFC 6749 in several ways:
  - Token endpoint accepts JSON (not form-urlencoded)
  - Authorization URL requires `code=true` query param
  - PKCE verifier is reused as state parameter
  - Token exchange body includes `state` field
  - Callback returns code#state (hash-separated, not query params)
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import webbrowser
from pathlib import Path
from urllib.parse import urlencode

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
AUTH_URL = "https://claude.ai/oauth/authorize"
TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"
REDIRECT_URI = "https://console.anthropic.com/oauth/code/callback"
SCOPES = "org:create_api_key user:profile user:inference"

_TOKEN_FILE = Path.home() / ".nanobot" / "anthropic_oauth.json"
_REFRESH_MARGIN_S = 300  # refresh 5 minutes before expiry


class AnthropicOAuthExpired(Exception):
    """Raised when OAuth token cannot be refreshed."""
    pass


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

def generate_pkce() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256).

    Anthropic reuses the verifier as the state parameter, so it serves
    double duty as both PKCE verifier and CSRF state.
    """
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def build_auth_url(code_challenge: str, state: str) -> str:
    """Build the authorization URL with all required params."""
    params = {
        "code": "true",  # Anthropic-specific
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


# ---------------------------------------------------------------------------
# Token exchange / refresh
# ---------------------------------------------------------------------------

def exchange_code(code: str, state: str, code_verifier: str) -> dict:
    """Exchange authorization code for tokens via POST JSON."""
    payload = {
        "code": code,
        "state": state,
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": code_verifier,
    }
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.post(TOKEN_URL, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Token exchange failed (HTTP {resp.status_code}): {resp.text}"
            )
        return resp.json()


def refresh_access_token(refresh_token: str) -> dict:
    """Renew access token using refresh token."""
    payload = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "refresh_token": refresh_token,
    }
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        resp = client.post(TOKEN_URL, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(
                f"Token refresh failed (HTTP {resp.status_code}): {resp.text}"
            )
        return resp.json()


# ---------------------------------------------------------------------------
# Token storage
# ---------------------------------------------------------------------------

def _save_tokens(token_data: dict) -> None:
    """Save token data to disk with 0600 permissions."""
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "expires_at": int(time.time()) + token_data.get("expires_in", 3600),
        "scope": token_data.get("scope", SCOPES),
    }
    _TOKEN_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.chmod(_TOKEN_FILE, 0o600)


def _load_tokens() -> dict | None:
    """Load stored tokens, or None if missing."""
    if not _TOKEN_FILE.exists():
        return None
    try:
        return json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_anthropic_token() -> str:
    """Return a valid access token (from cache, or refresh if expiring).

    Raises AnthropicOAuthExpired if no valid token and refresh fails.
    """
    tokens = _load_tokens()
    if not tokens or not tokens.get("access_token"):
        raise AnthropicOAuthExpired(
            "No Anthropic OAuth token found. Run: nanobot provider login anthropic-oauth"
        )

    # Check expiry — refresh proactively if < 5 min left
    expires_at = tokens.get("expires_at", 0)
    if time.time() < expires_at - _REFRESH_MARGIN_S:
        return tokens["access_token"]

    # Try refresh
    refresh_tok = tokens.get("refresh_token")
    if not refresh_tok:
        raise AnthropicOAuthExpired(
            "Anthropic OAuth token expired (no refresh token). Run: nanobot provider login anthropic-oauth"
        )

    try:
        new_data = refresh_access_token(refresh_tok)
        _save_tokens(new_data)
        return new_data["access_token"]
    except Exception as exc:
        raise AnthropicOAuthExpired(
            f"Failed to refresh Anthropic OAuth token: {exc}. Run: nanobot provider login anthropic-oauth"
        ) from exc


def login_interactive(print_fn=print, prompt_fn=input) -> None:
    """Interactive login: opens browser, user pastes code#state from callback page."""
    code_verifier, code_challenge = generate_pkce()
    # Anthropic reuses PKCE verifier as state
    state = code_verifier
    auth_url = build_auth_url(code_challenge, state)

    print_fn("Opening browser for Anthropic OAuth login...\n")
    print_fn(f"If the browser doesn't open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    print_fn("After authorizing, copy the code shown on the callback page and paste it below.\n")
    callback_input = prompt_fn(
        "Paste the code here"
    ).strip()

    # Parse code#state format
    if "#" in callback_input:
        code, returned_state = callback_input.split("#", 1)
    elif callback_input.startswith("http"):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(callback_input)
        params = parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        returned_state = params.get("state", [None])[0]
    else:
        code = callback_input
        returned_state = state  # assume state matches if not provided

    if not code:
        raise RuntimeError("No authorization code found in the pasted value.")

    if returned_state and returned_state != state:
        raise RuntimeError("State mismatch — possible CSRF attack")

    # Exchange code for tokens
    print_fn("Exchanging authorization code for tokens...")
    token_data = exchange_code(code, returned_state or state, code_verifier)
    _save_tokens(token_data)
    print_fn("Tokens saved successfully.")
