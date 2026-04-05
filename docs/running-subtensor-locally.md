# Running subtensor node locally

For General information on running Subtensors, see
[**Subtensor Nodes** section in Bittensor Developer Documentation](https://docs.bittensor.com/subtensor-nodes).

### Running a localnet subtensor node

Running a localnet in docker compose is the easiest way to quickly iterate on
chain state, like building on the evm.

1. Install Docker and Compose, and clone this repository.

1. **Pre-built images (no Rust compile):** see [RUN_LOCAL.md](../RUN_LOCAL.md) — log in to `ghcr.io`, then
   `docker compose -f docker-compose.localnet.yml pull` and `up -d`.

1. **Build from source:** use [`Dockerfile`](../Dockerfile) target `subtensor-local` or [`Dockerfile-localnet`](../Dockerfile-localnet), or add a `build:` section back to `docker-compose.localnet.yml` if you maintain your own compose overlay.

Now you should have a full local validator running. To test your connection, you
can use the following script to check `//Alice`'s balance. Alice is a sudo
account in localnet.

```py
# pip install substrate-interface
from substrateinterface import Keypair, SubstrateInterface

substrate = SubstrateInterface(url="ws://127.0.0.1:9945")
hotkey = Keypair.create_from_uri('//Alice')
result = substrate.query("System", "Account", [hotkey.ss58_address])
print(result.value)
```
