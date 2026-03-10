#!/usr/bin/env python3
"""Sync Codex CLI credentials (~/.codex/auth.json) to nanobot's oauth-cli-kit token."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


CODEX_CLI_PATH = Path.home() / ".codex" / "auth.json"
NANOBOT_TOKEN_PATH = Path.home() / "Library" / "Application Support" / "oauth-cli-kit" / "auth" / "codex.json"


def main() -> None:
    if not CODEX_CLI_PATH.exists():
        print(f"ERRO: {CODEX_CLI_PATH} não encontrado. Faça login no Codex CLI primeiro.")
        sys.exit(1)

    data = json.loads(CODEX_CLI_PATH.read_text(encoding="utf-8"))
    tokens = data.get("tokens") or {}
    access = tokens.get("access_token")
    refresh = tokens.get("refresh_token")
    account_id = tokens.get("account_id")

    if not access or not refresh or not account_id:
        print(f"ERRO: {CODEX_CLI_PATH} não contém access_token/refresh_token/account_id.")
        sys.exit(1)

    # Usa mtime do auth.json + 1h como expires (mesmo comportamento do oauth_cli_kit)
    try:
        mtime = CODEX_CLI_PATH.stat().st_mtime
        expires = int(mtime * 1000 + 60 * 60 * 1000)
    except Exception:
        expires = int(time.time() * 1000 + 60 * 60 * 1000)

    payload = {
        "access": access,
        "refresh": refresh,
        "expires": expires,
        "account_id": account_id,
    }

    NANOBOT_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Backup se já existir
    if NANOBOT_TOKEN_PATH.exists():
        backup = NANOBOT_TOKEN_PATH.with_suffix(".json.bak")
        backup.write_text(NANOBOT_TOKEN_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Backup salvo em: {backup}")

    NANOBOT_TOKEN_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    try:
        os.chmod(NANOBOT_TOKEN_PATH, 0o600)
    except Exception:
        pass

    print(f"Sincronizado com sucesso!")
    print(f"  account_id : {account_id}")
    print(f"  token path : {NANOBOT_TOKEN_PATH}")
    now_ms = int(time.time() * 1000)
    ttl_h = (expires - now_ms) / 3_600_000
    if ttl_h < 0:
        print(f"  expires    : já expirado (o nanobot fará refresh automático)")
    else:
        print(f"  expires in : {ttl_h:.1f}h")


if __name__ == "__main__":
    main()
