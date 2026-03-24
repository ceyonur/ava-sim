from web3 import Web3
import time
import threading

# CONFIGURATION
RPC_URL = "http://127.0.0.1:9660/ext/bc/98qnjenm7MBd8G2cPZoRvZrgJC33JGSAAKghsQ6eojbLCeRNp/rpc"
PRIVATE_KEY = "342056fab2ae8fa8fe52a80065a50e7338504306f0a204056e3bf2d58ca9fdb6"
TO_ADDRESS = "0xDA5c46764f0005F2185a2066B168922dDaE58B37"
TPS = 1  # transactions per second
AMOUNT_AVAX = 0 # per transaction

# Setup web3
w3 = Web3(Web3.HTTPProvider(RPC_URL))
acct = w3.eth.account.from_key(PRIVATE_KEY)
SENDER = acct.address

print(f"Connected: {w3.is_connected()} — Using address {SENDER}")

def send_tx(nonce):
    try:
        tx = {
            "to": TO_ADDRESS,
            "value": w3.to_wei(AMOUNT_AVAX, "ether"),
            "gas": 21000,
            # use only base fee
            "maxPriorityFeePerGas": 0,
            "maxFeePerGas": 36000000000,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        }

        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"✅ Sent tx: {tx_hash.hex()}")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    nonce = w3.eth.get_transaction_count(SENDER)
    interval = 1.0 / TPS

    print(f"Starting at {TPS} tx/sec...")

    while True:
        threading.Thread(target=send_tx, args=(nonce,)).start()
        nonce += 1
        time.sleep(interval)

if __name__ == "__main__":
    main()