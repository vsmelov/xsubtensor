import os
import sys

import bittensor as bt

netuid = int(sys.argv[1]) if len(sys.argv) > 1 else 1

# Host: ws://127.0.0.1:9944 — из Docker: SUBTENSOR_CHAIN_ENDPOINT=ws://subtensor-localnet:9944
endpoint = os.environ.get(
    "SUBTENSOR_CHAIN_ENDPOINT", "ws://127.0.0.1:9944"
)
subtensor = bt.subtensor(network=endpoint)
metagraph = subtensor.metagraph(netuid=netuid)
print(f"netuid={netuid} n={int(metagraph.n)} endpoint={endpoint}")
# To track miner performance (approaching deregistration)
print("I (incentive):", metagraph.I)
print("E (emission):", metagraph.E)

# To track validator performance (impacted by Yuma Consensus clipping)
print("D (dividends):", metagraph.D)