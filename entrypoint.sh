#!/bin/sh
set -eu

# Railway secrets are environment variables, while google-auth expects a file.
# Keep the decoded credential only in the ephemeral container filesystem.
if [ -n "${GOOGLE_APPLICATION_CREDENTIALS_B64:-}" ]; then
  credentials_path=/tmp/google-application-credentials.json
  printf '%s' "$GOOGLE_APPLICATION_CREDENTIALS_B64" | base64 -d > "$credentials_path"
  export GOOGLE_APPLICATION_CREDENTIALS="$credentials_path"
fi

exec python -m analytics_mcp.http_server
