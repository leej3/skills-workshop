#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'commit-provenance: %s\n' "$1" >&2
  exit 1
}

thread_id="${CODEX_THREAD_ID:-}"
[ -n "$thread_id" ] || fail 'CODEX_THREAD_ID is unavailable'

codex_root="${CODEX_HOME:-$HOME/.codex}"
session_file=$(find "$codex_root/sessions" -type f \
  -name "*-${thread_id}.jsonl" -print -quit 2>/dev/null || true)
script_dir=$(cd "$(dirname "$0")" && pwd)
provenance_mode='runtime'
if [ -n "$session_file" ]; then
  [ -z "${CODEX_TASK_SERVICE_CONTEXT:-}" ] \
    || fail 'local session transcript is available; remove task-service fallback context'
  turn_context=$(jq -sc '[.[] | select(.type == "turn_context")][-1].payload' \
    "$session_file")
else
  command -v python3 >/dev/null || fail 'python3 is required for runtime-log fallback'
  if turn_context=$(python3 "$script_dir/runtime_context.py" \
    "$codex_root/logs_2.sqlite" "$thread_id" 2>&1); then
    [ -z "${CODEX_TASK_SERVICE_CONTEXT:-}" ] \
      || fail 'fresh runtime metadata is available; remove task-service fallback context'
    printf 'commit-provenance: runtime-log fallback for thread %s, turn %s\n' \
      "$thread_id" "$(jq -r '.turn_id' <<<"$turn_context")" >&2
  elif [ -n "${CODEX_TASK_SERVICE_CONTEXT:-}" ]; then
    turn_context=$(python3 "$script_dir/runtime_context.py" \
      --task-service-context "$CODEX_TASK_SERVICE_CONTEXT" "$thread_id") \
      || fail 'invalid explicit task-service context'
    provenance_mode='task-service-partial'
    printf 'commit-provenance: using task-service verified IDs; model and effort are unavailable\n' >&2
  else
    fail "$turn_context"
  fi
fi
model=$(jq -r '.model // empty' <<<"$turn_context")
effort=$(jq -r '.reasoning_effort // .effort // empty' <<<"$turn_context")
if [ "$provenance_mode" = 'task-service-partial' ]; then
  model='unavailable'
  effort='unavailable'
else
  [ -n "$model" ] || fail 'latest turn context does not contain a model'
  [ -n "$effort" ] || fail 'latest turn context does not contain reasoning effort'
fi

app_path='/Applications/ChatGPT.app'
desktop_version=$(/usr/libexec/PlistBuddy \
  -c 'Print :CFBundleShortVersionString' \
  "$app_path/Contents/Info.plist" 2>/dev/null || true)
runtime_path=''
for candidate in \
  "$app_path/Contents/Resources/codex-cli/bin/codex" \
  "$app_path/Contents/Resources/codex"; do
  if [ -x "$candidate" ]; then
    runtime_path=$candidate
    break
  fi
done
[ -n "$runtime_path" ] || fail 'cannot find bundled Codex runtime executable'
runtime_output=$("$runtime_path" --version 2>/dev/null) \
  || fail "cannot execute bundled Codex runtime: $runtime_path"
runtime_version=$(printf '%s\n' "$runtime_output" \
  | awk 'NR == 1 && $1 == "codex-cli" && NF == 2 { print $2 }')
[ -n "$desktop_version" ] || fail 'cannot identify Codex Desktop version'
[ -n "$runtime_version" ] || fail 'cannot identify bundled Codex runtime version'

printf 'Co-Authored-By: Codex Desktop %s (runtime codex-cli %s) / %s <codex@openai.com>\n' \
  "$desktop_version" "$runtime_version" "$model"
printf 'Codex-Reasoning-Effort: %s\n' "$effort"
if [ "$provenance_mode" = 'task-service-partial' ]; then
  printf 'Codex-Task-Service-Thread-ID: %s\n' "$(jq -r '.thread_id' <<<"$turn_context")"
  printf 'Codex-Task-Service-Turn-ID: %s\n' "$(jq -r '.turn_id' <<<"$turn_context")"
  printf 'Codex-Provenance-Evidence-Source: %s\n' "$(jq -r '.evidence_source' <<<"$turn_context")"
  printf 'Codex-Provenance-Evidence-Reference: %s\n' "$(jq -r '.evidence_reference' <<<"$turn_context")"
  printf 'Codex-Model-Status: unavailable\n'
  printf 'Codex-Model-Reason: %s\n' "$(jq -r '.model_unavailable_reason' <<<"$turn_context")"
  printf 'Codex-Reasoning-Effort-Status: unavailable\n'
  printf 'Codex-Reasoning-Effort-Reason: %s\n' "$(jq -r '.reasoning_effort_unavailable_reason' <<<"$turn_context")"
fi
