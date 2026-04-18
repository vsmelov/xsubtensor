# How to create and run a subnet (Bittensor localnet, this repo)

This guide summarizes how we bring up **Subtensor localnet** in Docker, create a subnet on-chain with **`btcli`**, start emissions, register neurons, and run subnet containers (subnet-math, subnet-navigation, subnet-vla). Step-by-step details for **subnet-math** live in [`SUBNET_MATH_LOCALNET.md`](SUBNET_MATH_LOCALNET.md) (Russian); day-to-day compose and probes are in [`SUBNET_MATH_OPERATIONS.md`](SUBNET_MATH_OPERATIONS.md), [`RUN_LOCAL.md`](RUN_LOCAL.md), and [`REQUEST_TO_SUBNET.md`](REQUEST_TO_SUBNET.md).

---

## 1. Principles

- **No one-shot bootstrap scripts** are maintained as the source of truth. Long `docker compose run` flows break mid-way; the reliable approach is **manual steps with a verification after each block** (see [`SUBNET_MATH_LOCALNET.md`](SUBNET_MATH_LOCALNET.md)).
- From containers on the **same Docker network** as the node, use **`ws://subtensor-localnet:9944`** (container name from [`docker-compose.localnet.yml`](docker-compose.localnet.yml)). From the host, use **`ws://127.0.0.1:9944`**.
- **`btcli` 9.7.x:** use **`subnets list`**, not the deprecated `subnet list`.
- **`subnet create` / `subnet start` / `subnets register`** can take **minutes**. **`--no-prompt` alone is not enough:** you must pass **every subnet identity field** as flags, or the CLI will wait on interactive prompts and look “hung”.

---

## 2. Prerequisites

1. **Docker** with Compose v2.
2. **GHCR login** for `ghcr.io/opentensor/subtensor-localnet` (see [`RUN_LOCAL.md`](RUN_LOCAL.md)).
3. Repo root as working directory for all commands below.

### 2.1 Start localnet

```powershell
docker compose -f docker-compose.localnet.yml pull
docker compose -f docker-compose.localnet.yml up -d
```

- **Fast blocks** (~250 ms): default in compose is `command: ["True", "--no-purge"]` on the `localnet` service. For ~12 s blocks (closer to mainnet timing), set `command: ["False", "--no-purge"]`.
- After **`down -v`** or an image tag change, **chain data is reset**; you must **create subnets and register neurons again** and update **`NETUID`** in your `.env.*` files.

### 2.2 Optional: HTTP faucet (`//Alice`)

Useful to fund coldkeys from the host:

```powershell
docker compose -f docker-compose.localnet.yml --profile faucet up -d
```

Health: `Invoke-RestMethod http://127.0.0.1:8090/health` (PowerShell).

### 2.3 Build the image that ships `btcli` (example: subnet-math)

```powershell
docker compose -f docker-compose.subnet-math.yml build math-miner
```

---

## 3. Environment files

The repo tracks **examples only**; copy and edit locally (never commit real keys):

| Stack | Example | Your file |
|--------|---------|-----------|
| subnet-math | [`.env.subnet-math.example`](.env.subnet-math.example) | `.env.subnet-math` |
| subnet-navigation | [`.env.subnet-navigation.example`](.env.subnet-navigation.example) | `.env.subnet-navigation` |
| subnet-vla | [`.env.subnet-vla.example`](.env.subnet-vla.example) | `.env.subnet-vla` |

Set **`NETUID`** after `subnet create` (from `subnet-create.log` or `subnets list --json-out`). Set **`SUBTENSOR_DOCKER_NETWORK`** to the network where `subtensor-localnet` runs (often `xsubtensor_default`; check `docker network ls`).

---

## 4. Run `btcli` inside Docker (pattern)

Use **`-T`** (no TTY), **`HOME=/root`**, wallet path **`-p /root/.bittensor/wallets`**, and **`--entrypoint btcli`** on the service that has `btcli` (e.g. `math-miner`, `nav-miner`).

**Check chain connectivity:**

```powershell
docker compose -f docker-compose.subnet-math.yml run --rm -T -e HOME=/root --entrypoint btcli math-miner subnets list --network ws://subtensor-localnet:9944 --json-out
```

---

## 5. Wallets and TAO

Create **owner**, **miner**, and **validator** coldkeys + hotkey `default` (names must match your `.env.*`). Example names for math: `math-owner`, `math-miner`, `math-val` — full commands in [`SUBNET_MATH_LOCALNET.md`](SUBNET_MATH_LOCALNET.md) section 2.

Fund coldkeys via the faucet, e.g.:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8090/v1/transfer" -Method Post -ContentType "application/json" -Body '{"dest":"<SS58_OWNER>","amount_tao":"800000"}'
```

Repeat for miner and validator; verify with `wallet overview` on `ws://subtensor-localnet:9944`.

---

## 6. Non-interactive `subnet create` (`btcli` 9.7.x)

Pass **all** identity flags; placeholders are fine for dev.

| Flag | Example | If omitted |
|------|---------|------------|
| `--subnet-name` | `subnet-math` | Prompts for name |
| `--github-repo` | `https://github.com/opentensor/bittensor` | Identity prompts |
| `--subnet-contact` | `dev@local.test` | Prompts |
| `--subnet-url` | `https://example.com` | “Subnet URL (optional)” |
| `--discord-handle` | `none` | “Discord handle (optional)” |
| `--description` | `localnet-dev` | May prompt |
| `--additional-info` | `none` | May prompt |
| `--wallet-name` / `--hotkey` / `-p` | owner + `default` + `/root/.bittensor/wallets` | Wallet prompts |
| `--network` | `ws://subtensor-localnet:9944` | Wrong chain / RPC errors |

**Full `subnet create` (PowerShell, math owner):**

```powershell
docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math run --rm -T -e HOME=/root --entrypoint btcli math-miner subnet create `
  --subnet-name subnet-math `
  --wallet-name math-owner --hotkey default `
  --network ws://subtensor-localnet:9944 `
  --github-repo https://github.com/opentensor/bittensor `
  --subnet-contact dev@local.test `
  --subnet-url https://example.com `
  --discord-handle none `
  --description localnet-dev `
  --additional-info none `
  --no-prompt `
  -p /root/.bittensor/wallets
```

**Windows (recommended for long runs):** run the repo scripts in a separate `cmd` process so output goes to log files:

- [`scripts/subnet-create-localnet.cmd`](scripts/subnet-create-localnet.cmd) → **`subnet-create.log`**
- [`scripts/subnet-start-localnet.cmd`](scripts/subnet-start-localnet.cmd) → **`subnet-start.log`** (requires env **`SUBNET_LOCALNET_NETUID`**)

```powershell
Start-Process cmd.exe -ArgumentList "/c", "`"$PWD\scripts\subnet-create-localnet.cmd`"" -WindowStyle Minimized
Get-Content .\subnet-create.log -Tail 80 -Wait
```

Success line looks like: `Registered subnetwork with netuid: <N>`.

**Do not rely on PowerShell `Start-Job` for `docker compose`** on Windows; use `cmd` + redirect as in the `.cmd` scripts.

---

## 7. `NETUID`, `subnet start`, register, stake

1. **`subnets list --json-out`** — confirm **`netuid`**, write it into **`.env.subnet-math`** (or the stack you use).
2. **Owner: `subnet start`** — required so the subnet gets a **non-zero minting share** (see [`MINTING_SHARE_SUBNETS.md`](MINTING_SHARE_SUBNETS.md)).

   ```powershell
   docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math run --rm -T -e HOME=/root --entrypoint btcli math-miner subnet start --netuid <NETUID> --wallet-name math-owner --hotkey default --network ws://subtensor-localnet:9944 --no-prompt -p /root/.bittensor/wallets
   ```

   Or: `set SUBNET_LOCALNET_NETUID=<N>` then `scripts\subnet-start-localnet.cmd`.

3. **`subnets register`** for miner and validator on that **`netuid`**.
4. **`stake add`** for the validator(s) (amounts as in your doc / env).

Exact register and stake lines: [`SUBNET_MATH_LOCALNET.md`](SUBNET_MATH_LOCALNET.md) sections 5–6.

---

## 8. Run miners and validators (Docker)

When **`.env.subnet-math`** matches the wallets and **`NETUID`** you used in `btcli`:

```powershell
docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math up -d --build
```

Logs: `docker logs -f subtensor-math-validator`, `docker logs -f subtensor-math-miner`, etc.

**Operations** (metagraph, probes): [`SUBNET_MATH_OPERATIONS.md`](SUBNET_MATH_OPERATIONS.md).

---

## 9. Other subnets in this repo

### 9.1 subnet-navigation

Short checklist: [`SUBNET_NAVIGATION_LOCALNET.md`](SUBNET_NAVIGATION_LOCALNET.md).

- Copy `.env.subnet-navigation.example` → `.env.subnet-navigation`, set **`NETUID`**.
- Wallets: **`nav-owner`**, **`nav-miner`**, **`nav-miner-b`**, **`nav-val`**, **`nav-val-b`**; faucet; **`subnet create`** (see [`scripts/subnet-create-navigation-localnet.cmd`](scripts/subnet-create-navigation-localnet.cmd) → `subnet-create-navigation.log`).
- Owner must run **`subnet start`** for that netuid: [`scripts/subnet-start-navigation-localnet.cmd`](scripts/subnet-start-navigation-localnet.cmd).
- Then `docker compose -f docker-compose.subnet-navigation.yml --env-file .env.subnet-navigation up -d --build`.

### 9.2 subnet-vla

Stack and HTTP probes: [`REQUEST_TO_SUBNET.md`](REQUEST_TO_SUBNET.md) and [`docker-compose.subnet-vla.yml`](docker-compose.subnet-vla.yml). On-chain creation follows the **same btcli pattern** as math (correct service name, wallet names, and compose file for the vla stack).

---

## 10. Recreating localnet or a second subnet

- **`docker compose -f docker-compose.localnet.yml down -v`** resets subnet indices; after a new **`subnet create`**, read **`netuid`** again and update **`.env.*`**.
- A **second subnet** on the same chain: use a different **`--subnet-name`**, note the new **`netuid`**, and point the right compose project at it.
- [`scripts/subnet-create-localnet.cmd`](scripts/subnet-create-localnet.cmd) is hard-coded to **`subnet-math`**; for another name, copy the script or run `docker compose …` manually.

---

## 11. Related docs (quick index)

| Topic | File |
|--------|------|
| Localnet compose, GHCR, WS on Windows, fast blocks | [`RUN_LOCAL.md`](RUN_LOCAL.md) |
| Full math walkthrough (wallets → compose up) | [`SUBNET_MATH_LOCALNET.md`](SUBNET_MATH_LOCALNET.md) |
| After subnet exists: services, inspect | [`SUBNET_MATH_OPERATIONS.md`](SUBNET_MATH_OPERATIONS.md) |
| Why `subnet start` matters for emission | [`MINTING_SHARE_SUBNETS.md`](MINTING_SHARE_SUBNETS.md) |
| HTTP probes, faucet routes | [`REQUEST_TO_SUBNET.md`](REQUEST_TO_SUBNET.md), [`REQUEST_NET_GRAPH.md`](REQUEST_NET_GRAPH.md) |
| Cursor / agent hints for btcli | [`.cursor/rules/btcli-localnet.mdc`](.cursor/rules/btcli-localnet.mdc) |

---

## 12. `btcli --help`

Flag names drift between versions. Always verify:

```powershell
docker compose -f docker-compose.subnet-math.yml run --rm -T -e HOME=/root --entrypoint btcli math-miner subnet create --help
```
