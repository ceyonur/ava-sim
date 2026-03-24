import requests
import datetime

RPC = "https://api.avax.network/ext/bc/C/rpc"
X = 10000   # how many blocks back you want to look

def rpc(method, params):
    return requests.post(
        RPC,
        json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
        timeout=10
    ).json()["result"]

# 1. Get latest block number
latest = int(rpc("eth_getBlockByNumber", ["latest", False])["number"], 16)

# 2. Target block = latest - X
target = latest - X

block = rpc("eth_getBlockByNumber", [hex(target), False])
timestamp = int(block["timestamp"], 16)

print(f"Latest block: {latest}")
print(f"Target block: {target}")
print(f"Timestamp:    {timestamp} (unix seconds)")
print(f"Timestamp:    {datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
