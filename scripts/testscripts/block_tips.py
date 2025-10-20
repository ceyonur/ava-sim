#!/usr/bin/env python3
import argparse
import json
import math
import sys
from typing import Any, Dict, List, Optional

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
            timeout=30,
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

# ----------------------- Core logic -----------------------

def fetch_block(rpc: str, id_hex: str) -> Dict[str, Any]:
    return rpc_call(rpc, "eth_getBlockByNumber", [id_hex, True])

def fetch_block_receipts_fast(rpc: str, block_hash: str) -> Optional[List[Dict[str, Any]]]:
    # Not standard everywhere, but fast when supported
    try:
        return rpc_call(rpc, "eth_getBlockReceipts", [block_hash])
    except Exception:
        return None

def fetch_receipt(rpc: str, txhash: str) -> Dict[str, Any]:
    return rpc_call(rpc, "eth_getTransactionReceipt", [txhash])

def get_latest_number(rpc: str) -> int:
    return hex_to_int(rpc_call(rpc, "eth_blockNumber", []))

def compute_block_stats(rpc: str, block: Dict[str, Any]) -> Dict[str, Any]:
    base_fee = hex_to_int(block.get("baseFeePerGas") or "0x0")
    gas_used_header = hex_to_int(block.get("gasUsed") or "0x0")

    # Subnet-EVM/Coreth custom fields if present (may be 0/absent on other chains)
    ext_data_gas_used = hex_to_int(block.get("extDataGasUsed") or "0x0")
    block_gas_cost = hex_to_int(block.get("blockGasCost") or "0x0")

    total_gas_used = gas_used_header + ext_data_gas_used

    # Collect receipts
    receipts = fetch_block_receipts_fast(rpc, block["hash"])
    if not receipts:
        receipts = [fetch_receipt(rpc, tx["hash"]) for tx in block.get("transactions", [])]

    tips_wei: List[int] = []
    total_effective_gas_tip_value_wei = 0  # Σ tip * gasUsed

    ignore_below_wei = 0
    for rc in receipts:
        eff_hex = rc.get("effectiveGasPrice")
        if eff_hex is None:
            # fallback to tx.gasPrice (legacy)
            tx_index = {t["hash"]: t for t in block.get("transactions", [])}
            tx = tx_index.get(rc.get("transactionHash", ""))
            if not tx or not tx.get("gasPrice"):
                continue
            eff_wei = hex_to_int(tx["gasPrice"])
        else:
            eff_wei = hex_to_int(eff_hex)

        tip = eff_wei - base_fee
        if tip < ignore_below_wei:
            continue
        if tip < 0:
            tip = 0

        tips_wei.append(tip)

        gas_used_tx = hex_to_int(rc.get("gasUsed") or "0x0")
        total_effective_gas_tip_value_wei += tip * gas_used_tx

    tips_wei_sorted = sorted(tips_wei)
    n = len(tips_wei_sorted)
    mean_tip_wei = (sum(tips_wei_sorted) // n) if n else 0
    if n == 0:
        median_tip_wei = 0
    elif n % 2 == 1:
        median_tip_wei = tips_wei_sorted[n // 2]
    else:
        median_tip_wei = (tips_wei_sorted[n // 2 - 1] + tips_wei_sorted[n // 2]) // 2

    # Your estimatedTip formula
    # totalRequiredTips = blockGasCost * baseFee + totalGasUsed - 1
    # estimatedTip = totalRequiredTips // totalGasUsed
    if total_gas_used == 0:
        estimated_tip_wei = None
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
        "meanTipGwei": wei_to_gwei_str(mean_tip_wei),
        "medianTipGwei": wei_to_gwei_str(median_tip_wei),
        "medianTipWei": median_tip_wei,
        "totalEffectiveGasTipValueGwei": wei_to_gwei_str(sum(tips_wei)),
        "estimatedTipGwei": wei_to_gwei_str(estimated_tip_wei) if estimated_tip_wei is not None else None,
        "estimatedTipWei": estimated_tip_wei,
    }

# ----------------------- CLI -----------------------

def main():
    ap = argparse.ArgumentParser(description="Compute per-block tip stats and summary.")
    ap.add_argument("--rpc", required=True, help="EVM JSON-RPC URL (e.g., https://…/ext/bc/C/rpc)")
    ap.add_argument("--start", default="latest", help='"latest" or hex block number (e.g., 0x10d4f)')
    ap.add_argument("--count", type=int, default=1, help="Number of blocks to fetch from start backward if start=latest")
    args = ap.parse_args()

    # MUST call first per request
    max_priority_fee_wei = hex_to_int(rpc_call(args.rpc, "eth_maxPriorityFeePerGas", []))
    max_priority_fee_gwei = wei_to_gwei_str(max_priority_fee_wei)

    # Resolve start block number
    if str(args.start).lower() == "latest":
        start_num = get_latest_number(args.rpc)
    else:
        start_num = hex_to_int(args.start)

    medians_wei_all: List[int] = []
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
        if out.get("txCount", 0) > 0 and out.get("medianTipWei") is not None:
            medians_wei_all.append(int(out["medianTipWei"]))
        if out.get("estimatedTipWei") is not None:
            estimated_tips_wei_all.append(int(out["estimatedTipWei"]))

        per_block_rows.append(out)

    # Compute 60th percentiles over per-block medians and estimated tips
    p60_median_wei = percentile_nearest_rank(sorted(medians_wei_all), 60) if medians_wei_all else 0
    p60_estimated_wei = percentile_nearest_rank(sorted(estimated_tips_wei_all), 60) if estimated_tips_wei_all else 0

    # Print per-block lines
    for row in per_block_rows:
        print(json.dumps(row, separators=(",", ":"), ensure_ascii=False))

    # Print summary line
    summary = {
        "summaryOverBlocks": {
            "p60MedianTipGwei": wei_to_gwei_str(p60_median_wei),
            "p60EstimatedTipGwei": wei_to_gwei_str(p60_estimated_wei),
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
