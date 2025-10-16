#!/usr/bin/env python3
import argparse, json, math, sys, time, requests
from statistics import median
from decimal import Decimal, getcontext

getcontext().prec = 50  # high precision for wei math

# ---------- JSON-RPC ----------
def rpc_call(rpc, method, params):
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
          headers={"Content-Type": "application/json", "User-Agent": "block-tips-script/1.0"},
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

# ---------- Tips math ----------
def tx_tip_wei(effective_gas_price_wei, base_fee_wei):
    tip = int(effective_gas_price_wei) - int(base_fee_wei)
    return tip if tip > 0 else 0

def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0
    if p <= 0: return sorted_vals[0]
    if p >= 100: return sorted_vals[-1]
    k = math.ceil((p/100.0)*len(sorted_vals)) - 1
    return sorted_vals[max(0, min(k, len(sorted_vals)-1))]

# ---------- Core logic ----------
def fetch_block(rpc, id_):
    # full tx objects
    return rpc_call(rpc, "eth_getBlockByNumber", [id_, True])

def fetch_block_receipts_fast(rpc, block_hash):
    # Some providers / nodes support this (not standard everywhere).
    try:
        return rpc_call(rpc, "eth_getBlockReceipts", [block_hash])
    except Exception:
        return None

def fetch_receipt(rpc, txhash):
    return rpc_call(rpc, "eth_getTransactionReceipt", [txhash])

def compute_block_stats(rpc, block):
    base_fee = hex_to_int(block.get("baseFeePerGas") or "0x0")
    gas_used_header = hex_to_int(block.get("gasUsed") or "0x0")

    # Subnet-EVM/Coreth header extras if present
    ext_data_gas_used = hex_to_int(block.get("extDataGasUsed") or "0x0")  # may be absent
    block_gas_cost    = hex_to_int(block.get("blockGasCost")   or "0x0")  # may be absent

    total_gas_used = gas_used_header + ext_data_gas_used

    # Gather receipts (try fast path first)
    receipts = fetch_block_receipts_fast(rpc, block["hash"])
    if not receipts:
        receipts = [fetch_receipt(rpc, tx["hash"]) for tx in block.get("transactions", [])]

    tips_wei = []
    # (Optional) weighted-by-gas for your own checks (not printed unless you add it)
    # weighted_tip_sum_wei = 0

    for rc in receipts:
        eff = rc.get("effectiveGasPrice")
        if eff is None:
            # very old networks: try tx.gasPrice fallback
            tx = next((t for t in block["transactions"] if t["hash"] == rc["transactionHash"]), None)
            if not tx or not tx.get("gasPrice"):
                continue
            eff_wei = hex_to_int(tx["gasPrice"])
        else:
            eff_wei = hex_to_int(eff)

        tip = tx_tip_wei(eff_wei, base_fee)
        tips_wei.append(tip)
        # gas_used = hex_to_int(rc.get("gasUsed") or "0x0")
        # weighted_tip_sum_wei += tip * gas_used

    tips_wei_sorted = sorted(tips_wei)
    n = len(tips_wei_sorted)
    mean_tip_wei = (sum(tips_wei_sorted) // n) if n else 0
    median_tip_wei = (tips_wei_sorted[n//2] if n % 2 == 1
                      else ((tips_wei_sorted[n//2 - 1] + tips_wei_sorted[n//2]) // 2)) if n else 0

    # ----- Your formula -----
    # totalGasUsed = GasUsed + ExtDataGasUsed (done)
    # totalRequiredTips = blockGasCost * baseFee + totalGasUsed - 1
    # estimatedTip = totalRequiredTips / totalGasUsed   // integer div; (+totalGasUsed-1 rounded-up done above)
    if total_gas_used == 0:
        estimated_tip_wei = None  # undefined; avoid div-by-zero
    else:
        total_required_tips = (block_gas_cost * base_fee) + total_gas_used - 1
        estimated_tip_wei = total_required_tips // total_gas_used

    return {
        "blockNumber": hex_to_int(block["number"]),
        "blockHash": block["hash"].lower(),
        "txCount": n,
        "baseFeeGwei": wei_to_gwei_str(base_fee),
        "blockGasCost": block_gas_cost,
        "extDataGasUsed": ext_data_gas_used,
        "gasUsedHeader": gas_used_header,
        "totalGasUsed": total_gas_used,
        "meanTipGwei": wei_to_gwei_str(mean_tip_wei),
        "medianTipGwei": wei_to_gwei_str(median_tip_wei),
        "totalEffectiveGasTipValueGwei": wei_to_gwei_str(sum(tips_wei)),
        "estimatedTipGwei": (wei_to_gwei_str(estimated_tip_wei) if estimated_tip_wei is not None else None)
        # If you prefer the miner's *actual* tip revenue:
        # "totalPriorityFeesWei": str(weighted_tip_sum_wei)
    }

def main():
    ap = argparse.ArgumentParser(description="Block tip stats per block")
    ap.add_argument("--rpc", required=True, help="EVM JSON-RPC URL (eg. https://.../ext/bc/C/rpc)")
    ap.add_argument("--start", default="latest", help='"latest" or hex block number like 0x10d4f')
    ap.add_argument("--count", type=int, default=1, help="How many blocks (from start going backwards if start=latest)")
    args = ap.parse_args()

    if args.start.lower() == "latest":
        latest_hex = rpc_call(args.rpc, "eth_blockNumber", [])
        start_num = hex_to_int(latest_hex)
    else:
        start_num = hex_to_int(args.start)

    for i in range(args.count):
        num = start_num - i
        blk = fetch_block(args.rpc, int_to_hex(num))
        if not blk:
            continue
        out = compute_block_stats(args.rpc, blk)
        print(json.dumps(out, separators=(",", ":"), ensure_ascii=False))

if __name__ == "__main__":
    main()
