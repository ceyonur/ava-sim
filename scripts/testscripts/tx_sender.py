from web3 import Web3
import time
import threading

# CONFIGURATION
RPC_URL = "http://localhost:9660/ext/bc/2E1DARbp2qKqQ4tjUinZcr77thbGcM5K1VxXmTA45sHFezk3mj/rpc"
PRIVATE_KEY = "0248bc176e066e917ea1da4afb0199d68c3f4ae27e236cadb6decfc7c8b9e9ac"
TO_ADDRESS = "0x8db97C7cEcE249c2b98bDC0226Cc4C2A57BF52FC"
TPS = 100  # transactions per second
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
            "maxFeePerGas": 10000,
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