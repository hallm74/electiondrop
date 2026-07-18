#!/bin/zsh

set -euo pipefail

keychain_service="codex.fly.electiondrop-api"
keychain_account="hallm@1satcom.com"

export FLY_API_TOKEN="$(security find-generic-password \
  -a "$keychain_account" \
  -s "$keychain_service" \
  -w)"
export FLY_APP="electiondrop-api"

exec fly "$@"
