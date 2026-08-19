#!/usr/bin/env bash

set -euo pipefail

output_path="$1"
expected_text="$2"
prompt="$3"
max_attempts="${SMOKE_MAX_ATTEMPTS:-10}"
base_delay="${SMOKE_RETRY_BASE_SECONDS:-15}"
max_delay="${SMOKE_RETRY_MAX_SECONDS:-120}"
azd_command="${AZD_COMMAND:-azd}"

for ((attempt = 1; attempt <= max_attempts; attempt++)); do
  if "$azd_command" ai agent invoke \
    "$prompt" \
    --new-session \
    --no-prompt \
    --output raw >"$output_path" 2>&1 &&
    grep -q "event: response.completed" "$output_path" &&
    ! grep -q "event: response.failed" "$output_path" &&
    ! grep -q "Error: Function failed" "$output_path" &&
    ! grep -q '"error":{' "$output_path" &&
    { [[ -z "$expected_text" ]] || grep -q "$expected_text" "$output_path"; }; then
    exit 0
  fi

  if ((attempt == max_attempts)); then
    break
  fi

  delay=$((base_delay * (2 ** (attempt - 1))))
  if ((delay > max_delay)); then
    delay="$max_delay"
  fi
  if grep -qi "throughput limit" "$output_path"; then
    echo "::warning::Agent invocation was throttled; retrying in ${delay}s."
  else
    echo "::warning::Agent invocation failed; retrying in ${delay}s."
  fi
  sleep "$delay"
done

cat "$output_path"
exit 1
