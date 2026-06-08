#!/usr/bin/env bash
# Provision a Hermes profile for use as an OpenControl ACP agent backend.
#
# A Hermes profile is a state directory (config.yaml + .env + skills + sessions)
# selected at dispatch via HERMES_HOME. OpenControl points HERMES_HOME at
# ${HERMES_PROFILES_ROOT:-~/.hermes/profiles}/<name>, so this script writes the
# profile there.
#
# Usage:
#   scripts/hermes-provision-profile.sh <profile-name>
#
# Configuration (env vars, with OpenRouter defaults):
#   HERMES_PROVIDER     provider id          (default: openrouter)
#   HERMES_MODEL        default model slug    (default: deepseek/deepseek-v4-flash)
#   HERMES_BASE_URL     OpenAI-compatible URL (default: https://openrouter.ai/api/v1)
#   HERMES_KEY_ENV      env var holding the key (default: OPENROUTER_API_KEY)
#   <HERMES_KEY_ENV>    the actual API key value (required)
#   HERMES_VERSION      pinned hermes-agent version (default: 0.15.2)
set -euo pipefail

PROFILE="${1:?usage: hermes-provision-profile.sh <profile-name>}"
PROVIDER="${HERMES_PROVIDER:-openrouter}"
MODEL="${HERMES_MODEL:-deepseek/deepseek-v4-flash}"
BASE_URL="${HERMES_BASE_URL:-https://openrouter.ai/api/v1}"
KEY_ENV="${HERMES_KEY_ENV:-OPENROUTER_API_KEY}"
VERSION="${HERMES_VERSION:-0.15.2}"

KEY_VALUE="${!KEY_ENV:-}"
if [ -z "$KEY_VALUE" ]; then
  echo "error: \$$KEY_ENV is empty — export the provider key before provisioning" >&2
  exit 1
fi

ROOT="${HERMES_PROFILES_ROOT:-$HOME/.hermes/profiles}"
HOME_DIR="$ROOT/$PROFILE"
mkdir -p "$HOME_DIR"

HERMES=(uvx --from "hermes-agent[acp,mcp]==$VERSION" hermes)

HERMES_HOME="$HOME_DIR" "${HERMES[@]}" config set provider "$PROVIDER" >/dev/null
HERMES_HOME="$HOME_DIR" "${HERMES[@]}" config set model.default "$MODEL" >/dev/null
HERMES_HOME="$HOME_DIR" "${HERMES[@]}" config set base_url "$BASE_URL" >/dev/null

umask 077
printf '%s=%s\n' "$KEY_ENV" "$KEY_VALUE" > "$HOME_DIR/.env"

echo "Provisioned Hermes profile '$PROFILE' at $HOME_DIR (provider=$PROVIDER, model=$MODEL)."
echo "Reference it from an agent config with:  backend: hermes / profile: $PROFILE"
