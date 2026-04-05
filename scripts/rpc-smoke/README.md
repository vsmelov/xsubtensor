# Local RPC smoke tests

Small [Polkadot JS API](https://polkadot.js.org/docs/api) scripts to verify that your **WebSocket RPC** (e.g. Docker localnet on **9944**) is up before you use Polkadot Apps or a custom dapp.

## Setup

```powershell
cd scripts/rpc-smoke
npm install
```

## Commands

**One-shot health check** (chain name, head block, `//Alice` free balance):

```powershell
npm run check
```

**Bob’s RPC port** (same chain, second validator):

```powershell
$env:WS_URL = "ws://127.0.0.1:9945"; npm run check
```

**Faster failure** if the node is down:

```powershell
$env:TIMEOUT_MS = "5000"; npm run check
```

**Watch a few new blocks** (confirms live consensus):

```powershell
npm run new-heads
```

## Interpreting failures

- **`1006` / abnormal closure / ECONNREFUSED** — nothing listening on the URL, wrong port, or Docker container not running / ports not mapped.
- Your app and these scripts must use the **same** `WS_URL` as a running node (see [`RUN_LOCAL.md`](../../RUN_LOCAL.md)).

## TAO on local testnet (no faucet)

Local **Bittensor** chainspec pre-funds well-known dev seeds (see `node/src/chain_spec/localnet.rs` in this repo):

| Seed      | Approx. initial balance (9 decimals) |
| --------- | ------------------------------------ |
| `//Alice` | 1_000_000 TAO                        |
| `//Bob`   | 1_000_000 TAO                        |
| `//Charlie` | 1_000_000 TAO                      |
| `//Dave`, `//Eve`, `//Ferdie` | 2_000 TAO each        |

- **Polkadot{.js} extension:** import account from seed `//Alice` (dev only — never use on mainnet).
- **btcli:** e.g. `btcli wallet balance --wallet.name alice --network ws://127.0.0.1:9944` after creating a wallet from the Alice URI (see [provision wallets](https://docs.learnbittensor.org/local-build/provision-wallets/)).

There is no separate “faucet” on this localnet: balances come from **genesis**.
