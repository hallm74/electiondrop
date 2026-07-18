#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "Usage: $0 KEY_JSON RCLONE_CONFIG [DJANGO_ENV]" >&2
  exit 2
fi

key_json=$1
rclone_config=$2

umask 077
mkdir -p "$(dirname "$rclone_config")"

jq -r '
  (if type == "array" then .[0] else . end) |
  "[electiondrop-linode]\n" +
  "type = s3\n" +
  "provider = Other\n" +
  "access_key_id = \(.access_key)\n" +
  "secret_access_key = \(.secret_key)\n" +
  "endpoint = https://us-ord-10.linodeobjects.com\n" +
  "no_check_bucket = true\n"
' "$key_json" > "$rclone_config"

chmod 600 "$rclone_config"

if [[ $# -eq 3 ]]; then
  django_env=$3
  mkdir -p "$(dirname "$django_env")"
  jq -r '
    (if type == "array" then .[0] else . end) |
    "LINODE_S3_BUCKET=electiondrop-archive\n" +
    "LINODE_S3_ENDPOINT=https://us-ord-10.linodeobjects.com\n" +
    "LINODE_S3_CUSTOM_DOMAIN=electiondrop-archive.us-ord-10.linodeobjects.com\n" +
    "LINODE_S3_ACCESS_KEY_ID=\(.access_key)\n" +
    "LINODE_S3_SECRET_ACCESS_KEY=\(.secret_key)\n"
  ' "$key_json" > "$django_env"
  chmod 600 "$django_env"
fi
