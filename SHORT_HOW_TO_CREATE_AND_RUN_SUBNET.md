# Short guide: create a subnet and run nodes (Konnex Testnet)

Quick cheat sheet for users after **Konnex Testnet** goes live: install **`btcli`**, create wallets, and fund the owner coldkey with enough **KNX**. Full walkthrough (localnet, Docker, all flags) is in [`HOW_TO_CREATE_AND_RUN_SUBNET.md`](HOW_TO_CREATE_AND_RUN_SUBNET.md).

Use your own wallet names instead of `owner`, `miner`, `validator`. Read **`<NETUID>`** from `subnet create` output or `subnets list`.

If your node is **not** the one expected by `--subtensor.network test` for Konnex Testnet, pass your WebSocket explicitly, e.g. `--network ws://YOUR_NODE:9944` (see `btcli subnet create --help`).

---

## 1. Wallets (owner, miner, validator)

```bash
btcli wallet new-coldkey --wallet-name owner --no-use-password --n-words 12
btcli wallet new-hotkey --wallet-name owner --hotkey default --n-words 12

btcli wallet new-coldkey --wallet-name miner --no-use-password --n-words 12
btcli wallet new-hotkey --wallet-name miner --hotkey default --n-words 12

btcli wallet new-coldkey --wallet-name validator --no-use-password --n-words 12
btcli wallet new-hotkey --wallet-name validator --hotkey default --n-words 12
```

Fund the **owner** with **KNX** according to Konnex Testnet rules (faucet / team distribution).

---

## 2. Slot cost (optional)

```bash
btcli subnet lock_cost --subtensor.network test
```

---

## 3. Create a subnet (non-interactive)

`--no-prompt` **is not enough**: pass **all** subnet identity fields or the CLI will block on prompts.

```bash
btcli subnet create \
  --subtensor.network test \
  --subnet-name my-subnet \
  --wallet-name owner --hotkey default \
  --github-repo https://github.com/you/your-repo \
  --subnet-contact you@example.com \
  --subnet-url https://example.com \
  --discord-handle none \
  --description "My test subnet" \
  --additional-info none \
  --no-prompt
```

List subnets:

```bash
btcli subnets list --subtensor.network test --json-out
```

---

## 4. Start emissions (owner)

```bash
btcli subnet start --netuid <NETUID> --wallet-name owner --hotkey default --subtensor.network test --no-prompt
```

---

## 5. Register miner and validator

```bash
btcli subnets register --netuid <NETUID> --wallet-name miner --hotkey default --subtensor.network test --no-prompt

btcli subnets register --netuid <NETUID> --wallet-name validator --hotkey default --subtensor.network test --no-prompt
```

Validator stake (amount in **KNX** — set your own):

```bash
btcli stake add --amount 100 --netuid <NETUID> --wallet-name validator --hotkey default --subtensor.network test --no-prompt --unsafe
```

---

## 6. Run your subnet code

Follow your subnet template: `python neurons/miner.py` / `python neurons/validator.py` with **`NETUID`**, **`--subtensor.network test`** for Konnex Testnet (or your own endpoint), as in the template README.

Check status:

```bash
btcli wallet overview --wallet-name validator --subtensor.network test
```
