# Local subnet, miner, and validator (Bittensor)

This guide ties together **Subtensor** (the chain in this repo) and **subnet application code** (Python miner/validator, usually from the official template). It is aimed at running **one custom subnet** with **one miner** and **one validator** on your machine, e.g. as a stepping stone toward an **LLM text-to-text** subnet.

> Official tutorials (same flow, more detail): [Deploy locally](https://docs.bittensor.com/local-build/deploy), [Provision wallets](https://docs.bittensor.com/local-build/provision-wallets), [Create a subnet (locally)](https://docs.bittensor.com/local-build/create-subnet), [Mine & validate on localnet](https://docs.bittensor.com/local-build/mine-validate).

## How the pieces fit

| Piece | Role |
| ----- | ---- |
| **Subtensor** (Docker `docker-compose.localnet.yml` in this repo) | Blockchain: subnets, registrations, stakes, weights, emissions. |
| **`btcli`** | CLI to create subnets, register neurons, stake, inspect state. |
| **`subnet-template`** ([opentensor/subnet-template](https://github.com/opentensor/subnet-template)) | Minimal **Python** miner + validator + `protocol.py`; you replace the dummy logic with your task (e.g. LLM). |
| **Bittensor SDK** (`pip install bittensor`) | Library used by miner/validator to talk to chain and Axon. |

Subtensor does **not** run your LLM. Your **miner** serves the model; your **validator** queries miners and **sets weights** on-chain based on whatever scoring you implement.

## Prerequisites

1. **Local chain running** — follow [`RUN_LOCAL.md`](RUN_LOCAL.md) (`docker compose … up -d`).  
2. **WebSocket RPC reachable** — e.g. `ws://127.0.0.1:9944` (Alice) or `ws://127.0.0.1:9945` (Bob); same logical chain. Quick check: [`scripts/rpc-smoke`](scripts/rpc-smoke/README.md) (`npm run check`).  
3. **`btcli`** installed and on `PATH` (ships with current Bittensor tooling; see [docs](https://docs.bittensor.com/getting-started/installation)).  
4. **Python 3.10+** for the subnet repo.  
5. **Wallets** — at least three roles on paper: **subnet owner / creator**, **miner**, **validator** (docs often use names like `sn-creator`, `test-miner`, `test-validator`). Create coldkeys/hotkeys with `btcli wallet create` as in [provision wallets](https://docs.bittensor.com/local-build/provision-wallets).  
6. **TAO on creator + miners/validators** — fund them from the dev account `//Alice` (see [`RUN_LOCAL.md`](RUN_LOCAL.md) and genesis balances in `node/src/chain_spec/localnet.rs`). Subnet creation has a **dynamic burn / lock cost**; keep extra TAO for registrations and validator stake.

### Fast blocks (Docker localnet default)

Official docs recommend **`--no-mev-protection`** on several `btcli` commands when the node runs with **fast blocks**. Add it if your `btcli` version supports it and you see related errors.

### One `WS` URL everywhere

Pick one endpoint and use it for all `btcli` calls, e.g.:

```text
ws://127.0.0.1:9944
```

Some docs use `9945`; either works if the container maps both (see `docker-compose.localnet.yml`).

## Step 1 — Create the subnet on-chain

Run as the **creator** wallet (replace names and URL):

```powershell
btcli subnet create --subnet-name my-llm-subnet --wallet.name sn-creator --wallet.hotkey default --network ws://127.0.0.1:9944
```

Confirm the burn/lock prompt. List subnets and note the new **netuid**:

```powershell
btcli subnet list --network ws://127.0.0.1:9944
```

## Step 2 — Start emissions

Replace `NETUID` with your subnet’s id:

```powershell
btcli subnet start --netuid NETUID --wallet.name sn-creator --network ws://127.0.0.1:9944
```

Without this, you will not get the usual emission / staking behaviour described in the [create-subnet](https://docs.bittensor.com/local-build/create-subnet) docs.

## Step 3 — Register miner and validator hotkeys

Register **each** hotkey on **your** `NETUID`:

```powershell
btcli subnets register --netuid NETUID --wallet-name test-miner --hotkey default --network ws://127.0.0.1:9944
btcli subnets register --netuid NETUID --wallet-name test-validator --hotkey default --network ws://127.0.0.1:9944
```

(Adjust `--wallet-name` / `--hotkey` to match what you created.)

Inspect neurons:

```powershell
btcli subnet show --netuid NETUID --network ws://127.0.0.1:9944
```

## Step 4 — Validator permit (stake on validator)

Validators need a **validator permit** (see [validators overview](https://docs.bittensor.com/validators)). On localnet this is usually done by **staking TAO** to the validator hotkey:

```powershell
btcli stake add --netuid NETUID --wallet-name test-validator --hotkey default --partial --network ws://127.0.0.1:9944
```

Check overview; a `*` under **VPERMIT** (or equivalent) means the validator is permitted:

```powershell
btcli wallet overview --wallet.name test-validator --network ws://127.0.0.1:9944
```

If permit does not appear immediately, wait until the end of a **tempo** (subnet round), as in the [mine-validate](https://docs.bittensor.com/local-build/mine-validate) doc.

## Step 5 — Subnet template (miner + validator processes)

Clone the official template (or your fork):

```powershell
git clone https://github.com/opentensor/subnet-template.git
cd subnet-template
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install bittensor
```

### Pointing the SDK at your node

The template often uses `--subtensor.network local`, which assumes default local endpoints. If your stack expects an explicit URL, use the flag your `btcli` / SDK version documents (commonly **`--subtensor.chain_endpoint ws://127.0.0.1:9944`**) on **both** `miner.py` and `validator.py`.

### Run miner (separate terminal)

Exposes an **Axon** (default example port **8901**; change if busy):

```powershell
python miner.py --wallet.name test-miner --wallet.hotkey default --netuid NETUID --axon.port 8901 --subtensor.network local --logging.info
```

### Run validator (another terminal)

```powershell
python validator.py --wallet.name test-validator --wallet.hotkey default --netuid NETUID --subtensor.network local --logging.info
```

You should see the dummy protocol traffic (template multiplies numbers by two) and, after weights are set, changing **incentive / dividends** in:

```powershell
btcli subnet show --netuid NETUID --network ws://127.0.0.1:9944
```

## Toward an LLM text-to-text subnet

The template is **intentionally trivial** (`Dummy` synapse in `protocol.py`). For **text in → text out**:

1. **Define a synapse** in `protocol.py` (e.g. fields `prompt: str`, `response: str`, optional `model_id`, max lengths). Inherit from the Bittensor synapse type the SDK expects (see template and [Bittensor docs](https://docs.bittensor.com/)).  
2. **Miner** (`miner.py`): in the forward handler, run your **text generation** (local HF `transformers`, vLLM, HTTP call to an API, etc.), fill `response`, return. Mind **latency**, **GPU**, and **timeouts** validators will use.  
3. **Validator** (`validator.py`): send prompts (fixed set, sampled, or from a dataset), collect responses, **score** them (e.g. reference-based metrics, reward model, length penalties, refusal checks). Map scores to **weights** for registered UIDs (see template’s weight logic).  
4. **Operational**: open firewall rules for **Axon port**, use **distinct ports** if multiple miners on one host, log and rate-limit.  
5. **Production**: mainnet/testnet have different economics, registration costs, and subnet hyperparameters — re-read [Create a Subnet](https://docs.bittensor.com/subnets/create-a-subnet) for non-local deploys.

There is no single “LLM subnet” in this **subtensor** repo; your **Python repo** is the product. Search the ecosystem for open subnets similar to your task for inspiration (naming and APIs change over time).

## Troubleshooting (common)

| Symptom | What to check |
| ------- | ------------- |
| `1006` / cannot connect | Chain down or wrong `ws://` host/port; [`scripts/rpc-smoke`](scripts/rpc-smoke/README.md). |
| Insufficient balance for subnet create / register | Transfer TAO from Alice to the signing coldkey ([provision wallets](https://docs.bittensor.com/local-build/provision-wallets)). |
| Miner “not registered” | `btcli subnets register` on correct `NETUID` and endpoint. |
| `NeuronNoValidatorPermit` | Stake more on validator hotkey; wait for tempo ([mine-validate](https://docs.bittensor.com/local-build/mine-validate)). |
| `WeightVecLengthIsLow` | Often “no reachable miners” or weight vector too sparse; ensure miner Axon is up and validator can dial your IP/port. |
| SubWallet / HTTPS-only wallets | Local `ws://` is for **btcli / SDK / Polkadot JS**; wallets that require **wss** need a TLS proxy (see discussion in [`RUN_LOCAL.md`](RUN_LOCAL.md) context). |

## Reference links

- [opentensor/subnet-template](https://github.com/opentensor/subnet-template)  
- [Create a subnet (locally)](https://docs.bittensor.com/local-build/create-subnet)  
- [Mining and validating on localnet](https://docs.bittensor.com/local-build/mine-validate)  
- [Run Subtensor locally](RUN_LOCAL.md) (this fork)
