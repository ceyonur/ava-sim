#!/usr/bin/env python3
import argparse
import json
import math
import sys
from typing import Any, Dict, List

import requests

# ----------------------- Helpers -----------------------

def rpc_call(rpc: str, method: str, params: List[Any]) -> Any:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    }
    try:
        r = requests.post(
            rpc,
            json=payload,
            headers={"Content-Type": "application/json", "User-Agent": "block-tips-script/1.1"},
            timeout=40,
        )
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"RPC call failed for {method}: {e}")
    out = r.json()
    if "error" in out and out["error"]:
        raise RuntimeError(f"RPC error {out['error']}")
    return out["result"]

def hex_to_int(h):
    if h is None: return None
    if isinstance(h, int): return h
    h = h.lower()
    if h.startswith("0x"): h = h[2:]
    if h == "": return 0
    return int(h, 16)

def int_to_hex(i):
    return hex(int(i))

def wei_to_gwei_str(w):
    if w is None: return "0"
    w = int(w)
    q, r = divmod(w, 10**9)
    return f"{q}" if r == 0 else f"{q}.{str(r).zfill(9).rstrip('0')}"

def percentile_nearest_rank(sorted_vals: List[int], p: float) -> int:
    if not sorted_vals:
        return 0
    if p <= 0:
        return sorted_vals[0]
    if p >= 100:
        return sorted_vals[-1]
    k = math.ceil((p / 100.0) * len(sorted_vals)) - 1
    if k < 0:
        k = 0
    if k >= len(sorted_vals):
        k = len(sorted_vals) - 1
    return sorted_vals[k]

def percentile_linear_interpolation(sorted_vals: List[int], p: float) -> float:
    """
    Calculate percentile using linear interpolation method.
    This is the standard method that provides actual percentile values.

    Args:
        sorted_vals: List of sorted values
        p: Percentile (0-100)

    Returns:
        The interpolated percentile value
    """
    if not sorted_vals:
        return 0.0
    if p <= 0:
        return float(sorted_vals[0])
    if p >= 100:
        return float(sorted_vals[-1])

    n = len(sorted_vals)
    # Calculate the position in the sorted array
    pos = (p / 100.0) * (n - 1)

    # Get the lower and upper indices
    lower_idx = int(math.floor(pos))
    upper_idx = int(math.ceil(pos))

    # If we're exactly on an integer position, return that value
    if lower_idx == upper_idx:
        return float(sorted_vals[lower_idx])

    # Linear interpolation between the two values
    lower_val = float(sorted_vals[lower_idx])
    upper_val = float(sorted_vals[upper_idx])
    weight = pos - lower_idx

    return lower_val + weight * (upper_val - lower_val)

# ----------------------- Core logic -----------------------

def fetch_block(rpc: str, id_hex: str) -> Dict[str, Any]:
    return rpc_call(rpc, "eth_getBlockByNumber", [id_hex, True])


def get_latest_number(rpc: str) -> int:
    return hex_to_int(rpc_call(rpc, "eth_blockNumber", []))

def compute_block_stats(rpc: str, block: Dict[str, Any]) -> Dict[str, Any]:
    base_fee = hex_to_int(block.get("baseFeePerGas") or "0x0")
    gas_used_header = hex_to_int(block.get("gasUsed") or "0x0")

    # Subnet-EVM/Coreth custom fields if present (may be 0/absent on other chains)
    ext_data_gas_used = hex_to_int(block.get("extDataGasUsed") or "0x0")
    block_gas_cost = hex_to_int(block.get("blockGasCost") or "0x0")

    total_gas_used = gas_used_header + ext_data_gas_used

    # Calculate tips directly from transaction data (no receipt fetching needed)
    tips_wei: List[int] = []

    ignore_below_wei = 0
    for tx in block.get("transactions", []):
        # Get gas price from transaction
        gas_price_hex = tx.get("gasPrice")
        if not gas_price_hex:
            continue

        gas_price_wei = hex_to_int(gas_price_hex)

        # Calculate tip as gasPrice - baseFee
        tip = gas_price_wei - base_fee
        if tip < ignore_below_wei:
            continue
        if tip < 0:
            tip = 0

        tips_wei.append(tip)

    tips_wei_sorted = sorted(tips_wei)
    n = len(tips_wei_sorted)

    # Your estimatedTip formula
    # totalRequiredTips = blockGasCost * baseFee + totalGasUsed - 1
    # estimatedTip = totalRequiredTips // totalGasUsed
    if total_gas_used == 0:
        estimated_tip_wei = 0
    else:
        total_required_tips = (block_gas_cost * base_fee) + total_gas_used - 1
        estimated_tip_wei = total_required_tips // total_gas_used

    return {
        "blockNumber": hex_to_int(block["number"]),
        "blockHash": block["hash"],
        "txCount": n,
        "baseFeeGwei": wei_to_gwei_str(base_fee),
        "blockGasCost": block_gas_cost,
        "extDataGasUsed": ext_data_gas_used,
        "gasUsedHeader": gas_used_header,
        "totalGasUsed": total_gas_used,
        "tipsWei": tips_wei_sorted,
        "tipsGwei": [wei_to_gwei_str(t) for t in tips_wei_sorted],
        "totalEffectiveGasTipValueGwei": wei_to_gwei_str(sum(tips_wei)),
       #  "estimatedTipGwei": wei_to_gwei_str(estimated_tip_wei) if estimated_tip_wei is not None else None,
       # "estimatedTipWei": estimated_tip_wei,
    }

# ----------------------- CLI -----------------------

def main():
    ap = argparse.ArgumentParser(description="Compute per-block tip stats and summary.")
    ap.add_argument("--rpc", required=True, help="EVM JSON-RPC URL (e.g., https://…/ext/bc/C/rpc)")
    ap.add_argument("--start", default="latest", help='"latest" or hex block number (e.g., 0x10d4f)')
    ap.add_argument("--count", type=int, default=1, help="Number of blocks to fetch from start backward if start=latest")
    args = ap.parse_args()


    # Resolve start block number
    if str(args.start).lower() == "latest":
        start_num = get_latest_number(args.rpc)
    else:
        start_num = hex_to_int(args.start)

        # MUST call first per request
    max_priority_fee_wei = hex_to_int(rpc_call(args.rpc, "eth_maxPriorityFeePerGas", []))
    max_priority_fee_gwei = wei_to_gwei_str(max_priority_fee_wei)

    tips_wei_all: List[int] = []
    estimated_tips_wei_all: List[int] = []
    per_block_rows: List[Dict[str, Any]] = []

    # Iterate blocks
    for i in range(args.count):
        num = start_num - i
        blk = fetch_block(args.rpc, int_to_hex(num))
        if not blk:
            continue
        out = compute_block_stats(args.rpc, blk)

        # collect for summary p60s
        if out.get("txCount", 0) > 0 and out.get("tipsWei") is not None:
            tips_wei_all.extend(out["tipsWei"])

        if out.get("estimatedTipWei") is not None:
            estimated_tips_wei_all.append(int(out["estimatedTipWei"]))

        per_block_rows.append(out)

    # Compute 60th percentiles over per-block medians and estimated tips
    p60_median_wei = percentile_nearest_rank(sorted(tips_wei_all), 60) if tips_wei_all else 0
    p40_median_wei = percentile_nearest_rank(sorted(tips_wei_all), 40) if tips_wei_all else 0
    p80_median_wei = percentile_nearest_rank(sorted(tips_wei_all), 80) if tips_wei_all else 0
    p90_median_wei = percentile_nearest_rank(sorted(tips_wei_all), 90) if tips_wei_all else 0
    p60_estimated_wei = percentile_nearest_rank(sorted(estimated_tips_wei_all), 60) if estimated_tips_wei_all else 0
    p85_median_wei = percentile_nearest_rank(sorted(tips_wei_all), 85) if tips_wei_all else 0
    # Print per-block lines
    for row in per_block_rows:
        print(json.dumps(row, separators=(",", ":"), ensure_ascii=False))

    # Print summary line
    summary = {
        "summaryOverBlocks": {
            "p40MedianTipGwei": wei_to_gwei_str(p40_median_wei),
            "p60MedianTipGwei": wei_to_gwei_str(p60_median_wei),
            "p80MedianTipGwei": wei_to_gwei_str(p80_median_wei),
            "p85MedianTipGwei": wei_to_gwei_str(p85_median_wei),
            "p90MedianTipGwei": wei_to_gwei_str(p90_median_wei),
           # "p60EstimatedTipGwei": wei_to_gwei_str(p60_estimated_wei),
            "eth_maxPriorityFeePerGas_Gwei": max_priority_fee_gwei,
        }
    }
    print("\n"+ json.dumps(summary, separators=(",", ":"), ensure_ascii=False))

if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # allow piping to tools like `jq | head`
        try:
            sys.stdout.close()
        except Exception:
            pass
        sys.exit(0)
