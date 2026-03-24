import requests
import csv
import time
import os
import matplotlib.pyplot as plt

RPC = "https://api.avax.network/ext/bc/C/rpc"

def format_time(seconds):
    """Format seconds into a human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

def get_block(num):
    # Handle string block identifiers like "latest", "earliest", "pending"
    if isinstance(num, str):
        block_param = num
    else:
        block_param = hex(num)

    payload = {
        "jsonrpc": "2.0",
        "method": "eth_getBlockByNumber",
        "params": [block_param, False],
        "id": 1
    }
    while True:
        try:
            r = requests.post(RPC, json=payload, timeout=10).json()
            return r["result"]
        except Exception as e:
            print("Retrying:", e)
            time.sleep(1)

# --------------------------------------------------------
# 1. Check for existing data or fetch new data
# --------------------------------------------------------
timestamps = []
csv_file = "cchain_blocks.csv"

if os.path.exists(csv_file):
    print(f"Found existing {csv_file}, using local data...")
    try:
        with open(csv_file, "r") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header:
                for row in reader:
                    if row:
                        try:
                            ts = int(row[1])
                            # Use timestamp_milliseconds if available, otherwise timestamp * 1000
                            try:
                                tms = int(row[2])
                            except (ValueError, IndexError):
                                tms = ts * 1000
                            timestamps.append(tms)
                        except (ValueError, IndexError):
                            continue
        print(f"Loaded {len(timestamps)} blocks from {csv_file}")
    except Exception as e:
        print(f"Error reading existing file: {e}. Please delete it and run again to re-download.")
        exit(1)

else:
    print("No local data found. Starting download...")

    # Fetch latest block number
    latest_block = int(get_block("latest")["number"], 16)
    print("Latest block:", latest_block)

    BLOCK_COUNT = 10000
    start_block = latest_block - BLOCK_COUNT
    print(f"Downloading blocks {start_block} → {latest_block}")

    start_time = time.time()
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["block_number", "timestamp", "timestamp_milliseconds"])

        total_blocks_to_download = latest_block - start_block + 1

        for i, n in enumerate(range(start_block, latest_block + 1)):
            block = get_block(n)
            ts_sec = int(block["timestamp"], 16)

            # Use timestampMilliseconds if available, otherwise timestamp * 1000
            if "timestampMilliseconds" in block:
                ts_ms = int(block["timestampMilliseconds"], 16)
                tms_csv = ts_ms
            else:
                ts_ms = ts_sec * 1000
                tms_csv = None

            timestamps.append(ts_ms)
            writer.writerow([n, ts_sec, tms_csv])

            # Progress update every 100 blocks (or at the end)
            if i % 100 == 0 or n == latest_block:
                elapsed = time.time() - start_time
                downloaded = i + 1
                remaining = total_blocks_to_download - downloaded

                if downloaded > 0:
                    avg_time_per_block = elapsed / downloaded
                    eta_seconds = avg_time_per_block * remaining
                    eta_str = format_time(eta_seconds)
                else:
                    eta_str = "calculating..."

                elapsed_str = format_time(elapsed)
                print(f"Downloaded {downloaded}/{total_blocks_to_download} blocks... Elapsed: {elapsed_str}, ETA: {eta_str}")

    total_time = time.time() - start_time
    print(f"Saved to {csv_file} (Total download time: {format_time(total_time)})")

# --------------------------------------------------------
# 3. Compute block times
# --------------------------------------------------------
# timestamps are in milliseconds, convert differences to seconds
block_times = [(timestamps[i] - timestamps[i-1]) / 1000.0 for i in range(1, len(timestamps))]

# --------------------------------------------------------
# 4. Plot
# --------------------------------------------------------
if not block_times:
    print("No block times to plot.")
    exit()

avg_block_time = sum(block_times) / len(block_times)
print(f"Average block time: {avg_block_time:.4f} seconds")

# Moving average smoothing
window_size = 50
smoothed_times = []
if len(block_times) >= window_size:
    for i in range(len(block_times) - window_size + 1):
        window = block_times[i : i + window_size]
        smoothed_times.append(sum(window) / window_size)

plt.figure(figsize=(12, 5))
plt.plot(block_times, label="Block Time", alpha=0.3) # Reduce opacity of raw data
if smoothed_times:
    # Align the smoothed plot to end of the window
    plt.plot(range(window_size - 1, len(block_times)), smoothed_times, label=f"Smoothed (window={window_size})", color='orange', linewidth=2)

plt.axhline(y=avg_block_time, color='r', linestyle='--', label=f"Avg: {avg_block_time:.3f}s")
plt.title(f"Avalanche C-Chain Block Times (Last {len(block_times)} blocks)")
plt.xlabel("Block Index")
plt.ylabel("Block Time (seconds)")
plt.grid(True)
plt.legend()
plt.show()
