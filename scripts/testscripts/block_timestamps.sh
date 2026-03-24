#!/usr/bin/env bash
set -euo pipefail

# Requirements: curl, jq
URL="${URL:-https://api.avax.network:443/ext/bc/C/rpc}"
HDR="Content-Type: application/json"

# Configurable via env or flags:
START_HEX="${START_HEX:-0x0}"   # starting block (hex like 0x0, 0x1a, etc., or "latest", "pending", "earliest")
DELAY_SEC="${DELAY_SEC:-1}"     # delay between retries when block not yet available
COUNT="${COUNT:-0}"             # 0 = run forever; otherwise number of blocks to process

usage() {
  cat <<EOF
Usage: $(basename "$0") [--start 0xHEX|latest] [--delay SECONDS] [--count N] [--url URL]
Env vars also supported: START_HEX, DELAY_SEC, COUNT, URL

Examples:
  $(basename "$0") --start 0x0 --count 10
  $(basename "$0") --start latest --count 5
  $(basename "$0") --url https://subnets.avax.network/echo/testnet/rpc --start 0x0
  START_HEX=latest COUNT=0 DELAY_SEC=2 $(basename "$0")
EOF
}

# Parse flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --start) START_HEX="$2"; shift 2 ;;
    --delay) DELAY_SEC="$2"; shift 2 ;;
    --count) COUNT="$2"; shift 2 ;;
    --url) URL="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 1 ;;
  esac
done

# Helpers
hex2dec() { local h="${1#0x}"; echo $((16#$h)); }
dec2hex() { printf "0x%x" "$1"; }

rpc_call() {
  local block_hex="$1"
  curl -sS -H "$HDR" -X POST "$URL" \
    --data "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getBlockByNumber\",\"params\":[\"${block_hex}\",true],\"id\":1}"
}

extract_field() {
  local json="$1" field="$2"
  jq -r --arg f "$field" '.result[$f] // empty' <<<"$json"
}

wait_for_block() {
  local block_hex="$1" j
  while true; do
    j="$(rpc_call "$block_hex")" || true
    # Non-empty .result indicates the block exists
    if jq -e '.result != null' >/dev/null 2>&1 <<<"$j"; then
      echo "$j"
      return 0
    fi
    sleep "$DELAY_SEC"
  done
}

prev_ts_dec=""
prev_tms_dec=""
prev_hex=""
prev_blockgascost_dec=""
prev_mindelayexcess_dec=""

# Handle special block tags like "latest", "pending", "earliest"
if [[ "$START_HEX" == "latest" || "$START_HEX" == "pending" || "$START_HEX" == "earliest" ]]; then
  echo "Fetching ${START_HEX} block number..."
  latest_json="$(rpc_call "$START_HEX")"
  if ! jq -e '.result != null' >/dev/null 2>&1 <<<"$latest_json"; then
    echo "Error: Failed to fetch ${START_HEX} block"
    exit 1
  fi
  START_HEX="$(extract_field "$latest_json" "number")"
  if [[ -z "$START_HEX" ]]; then
    echo "Error: Could not extract block number from ${START_HEX} block response"
    exit 1
  fi
  echo "Starting from block ${START_HEX}"
fi

start_dec="$(hex2dec "$START_HEX")"
processed=0

while :; do
  block_hex="$(dec2hex "$start_dec")"

  # Fetch (wait if not ready yet)
  j="$(wait_for_block "$block_hex")"

  # Extract fields
  ts_hex="$(extract_field "$j" "timestamp")"
  tms_hex="$(extract_field "$j" "timestampMilliseconds")"
  blockgascost_hex="$(extract_field "$j" "blockGasCost")"
  mindelayexcess_hex="$(extract_field "$j" "minDelayExcess")"
  basefeepergas_hex="$(extract_field "$j" "baseFeePerGas")"

  # Convert to decimal (empty -> print as missing)
  ts_dec=""; tms_dec=""
  [[ -n "$ts_hex" ]] && ts_dec="$(hex2dec "$ts_hex")" || true
  [[ -n "$tms_hex" ]] && tms_dec="$(hex2dec "$tms_hex")" || true
  [[ -n "$blockgascost_hex" ]] && blockgascost_dec="$(hex2dec "$blockgascost_hex")" || true
  [[ -n "$mindelayexcess_hex" ]] && mindelayexcess_dec="$(hex2dec "$mindelayexcess_hex")" || true
  [[ -n "$basefeepergas_hex" ]] && basefee_wei_dec="$(hex2dec "$basefeepergas_hex")" || true
  # Print current
  echo "Block ${block_hex}:"
  echo "  baseFeePerGas          (dec): ${basefee_wei_dec:-<missing>}"
  echo "  timestamp              (dec): ${ts_dec:-<missing>}"
  echo "  timestampMilliseconds  (dec): ${tms_dec:-<missing>}"
  echo "  blockGasCost           (dec): ${blockgascost_dec:-<missing>}"
  echo "  minDelayExcess         (dec): ${mindelayexcess_dec:-<missing>}"
  # Warn and exit if blockgascost is not zero
  if [[ -n "${blockgascost_dec:-}" && $blockgascost_dec -ne 0 ]]; then
    echo "  WARN: blockGasCost is not zero!"
  fi

  # Compare with previous, if any
  if [[ -n "${prev_hex:-}" ]]; then
    if [[ -n "${prev_ts_dec:-}" && -n "${ts_dec:-}" ]]; then
      printf "  Δ seconds (vs %s): %s\n" "$prev_hex" "$((ts_dec - prev_ts_dec))"
    else
      echo "  Δ seconds: <cannot compute>"
    fi

    if [[ -n "${prev_tms_dec:-}" && -n "${tms_dec:-}" ]]; then
      printf "  Δ milliseconds (vs %s): %s\n" "$prev_hex" "$((tms_dec - prev_tms_dec))"
    else
      echo "  Δ milliseconds: <cannot compute>"
    fi

    if [[ -n "${prev_mindelayexcess_dec:-}" && -n "${mindelayexcess_dec:-}" ]]; then
      printf "  Δ minDelayExcess (vs %s): %s\n" "$prev_hex" "$((mindelayexcess_dec - prev_mindelayexcess_dec))"
    else
      echo "  Δ minDelayExcess: <cannot compute>"
    fi

    # sanity warnings
    if [[ -n "${prev_ts_dec:-}" && -n "${ts_dec:-}" && $ts_dec -lt $prev_ts_dec ]]; then
      echo "  WARN: timestamp decreased!"
    fi
    if [[ -n "${prev_tms_dec:-}" && -n "${tms_dec:-}" && $tms_dec -lt $prev_tms_dec ]]; then
      echo "  WARN: timestampMilliseconds decreased!"
    fi
  else
    echo "  (no previous block to diff against)"
  fi

  echo

  # Prepare for next iteration
  prev_ts_dec="${ts_dec:-}"
  prev_tms_dec="${tms_dec:-}"
  prev_mindelayexcess_dec="${mindelayexcess_dec:-}"
  prev_hex="$block_hex"

  start_dec=$((start_dec + 1))
  processed=$((processed + 1))

  # Stop if COUNT set and reached
  if [[ "$COUNT" -gt 0 && "$processed" -ge "$COUNT" ]]; then
    break
  fi
done
