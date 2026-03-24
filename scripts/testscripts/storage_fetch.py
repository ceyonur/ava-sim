#!/usr/bin/env python3
"""
Analyze C-Chain state growth patterns via RPC
"""

from web3 import Web3
import json

# Connect to C-Chain
w3 = Web3(Web3.HTTPProvider('https://api.avax.network/ext/bc/C/rpc'))

# Known large contracts to check
KNOWN_CONTRACTS = [
    "0x...",  # XENCrypto
    "0x...",  # AAVE
    # Add more
]

def estimate_storage_slots(address, sample_size=1000):
    """
    Estimate storage slot count by sampling.
    Full iteration would require archive node access.
    """
    # This is a rough estimate - checking specific known slots
    non_empty = 0
    for i in range(sample_size):
        slot = w3.eth.get_storage_at(address, i)
        if slot != b'\x00' * 32:
            non_empty += 1
    return non_empty

def analyze_recent_blocks(num_blocks=1000):
    """
    Analyze state changes in recent blocks
    """
    latest = w3.eth.block_number

    storage_changes = {}  # address -> (new_slots, deleted_slots)

    for block_num in range(latest - num_blocks, latest):
        block = w3.eth.get_block(block_num, full_transactions=True)

        for tx in block.transactions:
            if tx.to is None:
                continue  # Contract creation

            # Get trace to see storage changes
            # Requires debug_traceTransaction
            try:
                trace = w3.provider.make_request(
                    'debug_traceTransaction',
                    [tx.hash.hex(), {'tracer': 'prestateTracer', 'tracerConfig': {'diffMode': True}}]
                )
                # Analyze trace for SSTORE operations
            except:
                pass

    return storage_changes