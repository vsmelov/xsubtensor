# Running Subtensor locally (pre-built images only)

## RPC (WebSocket) — что подставлять в Konnex и скрипты

**Endpoint по умолчанию:** `ws://127.0.0.1:9944` (нода Alice в локальном `localnet`; тот же URL используют `scripts/rpc-smoke` и примеры ниже).

**Почему мы поменяли «дефолт» публикации порта:** в [`docker-compose.localnet.yml`](docker-compose.localnet.yml) RPC/WebSocket проброшен не на `0.0.0.0`, а на **`127.0.0.1:9944`** (только loopback на вашей машине). На **Windows с Docker Desktop** полный бинд и WebSocket с хоста на опубликованный порт часто дают обрывы соединения (типично код **`1006`** / `Abnormal Closure`), при том что сама нода в контейнере жива. Привязка только к `127.0.0.1` в таких сетапах чаще даёт стабильный доступ к RPC **с того же ПК**. Если нужен доступ с других машин в сети — добавьте свой [compose override](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/) с нужным `ports`.

---

Compose files pull images from GitHub Container Registry (`ghcr.io/opentensor/...`).

## Log in to GHCR first

Anonymous pulls often fail with `denied: denied`. Use a [GitHub Personal Access Token](https://github.com/settings/tokens) with the **`read:packages`** scope (classic PAT) or fine-grained token with **Packages: Read** for `opentensor/subtensor` and `opentensor/subtensor-localnet`.

```powershell
docker login ghcr.io -u YOUR_GITHUB_USERNAME
```

Paste the token when prompted for password (not your GitHub account password).

If you still see `denied` after logging in, try a fresh token, or run `docker logout ghcr.io` and log in again (stale or wrong credentials also produce `denied`). If the organization restricts package access, you may need build-from-source instead (see repository `Dockerfile` / `Dockerfile-localnet`).

## Requirements

- [Docker](https://docs.docker.com/get-docker/) with Compose v2 (Docker Desktop includes it).

## Local testnet (Alice + Bob in one container)

Uses [`docker-compose.localnet.yml`](docker-compose.localnet.yml). Default image: **`ghcr.io/opentensor/subtensor-localnet:v3.1.5`** ([package versions](https://github.com/opentensor/subtensor/pkgs/container/subtensor-localnet)) — same June 2025 line as SDK 9.7.x local work; override with env **`LOCALNET_IMAGE`** (e.g. `...:latest`). The container runs [`scripts/localnet.sh`](scripts/localnet.sh); RPC ports unchanged.

When you **change** the localnet image tag or hit runtime/state errors, reset chain data: `docker compose -f docker-compose.localnet.yml down -v` (only localnet volumes; host `~/.bittensor` is separate). Then re-register subnets / neurons.

Optional **HTTP faucet** (transfers signed as `//Alice`, bind only `127.0.0.1:8090`): see [`FAUCET_LOCAL.md`](FAUCET_LOCAL.md) (`docker compose --profile faucet up -d`).

```powershell
cd <path-to-this-repo>

docker compose -f docker-compose.localnet.yml pull
docker compose -f docker-compose.localnet.yml up -d
```

### Logs (localnet)

Stream logs from both nodes in one container (service name `localnet`):

```powershell
docker compose -f docker-compose.localnet.yml logs -f
```

Last *N* lines, then exit:

```powershell
docker compose -f docker-compose.localnet.yml logs --tail 200 localnet
```

By container name (set in compose as `subtensor-localnet`):

```powershell
docker logs -f subtensor-localnet
```

Add `--tail 200` to `docker logs` if you only want recent output.

- **Alice** — `9944` (WebSocket/RPC), p2p `30334`.
- **Bob** — `9945`, p2p `30335`.

Example: `ws://127.0.0.1:9944`. Sudo account: `//Alice`.

### Windows + Docker: WebSocket `1006` on `ws://127.0.0.1:9944`

Docker Desktop on Windows sometimes breaks **host → published port** for **WebSocket**, while **TCP** to the same port still looks “open”. The node in the container is often fine; the fragile part is **Win32 browser/Node → `localhost:9944`**.

**Prove the chain is OK (no VPS):** run the smoke test **inside** the compose network (uses `ws://localnet:9944`, not the host port):

```powershell
cd <path-to-this-repo>
docker compose -f docker-compose.localnet.yml up -d
docker compose -f docker-compose.localnet.yml --profile tools run --rm rpc-smoke-check
```

You should see `OK — WebSocket RPC is reachable` and `//Alice` balance. If this works but the host still fails, the issue is **host↔Docker WS**, not Subtensor.

**Compose change:** RPC ports are published as **`127.0.0.1:9944`** (loopback only). On some setups this behaves better than binding all interfaces. If you need LAN access, override ports in a [compose override](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/) file.

#### 0) Environment checklist (do this before chasing code)

1. **VPN — выключить полностью** (NordVPN / Outline / Amnezia и т.д.), не только «переподключить». Туннели часто ломают маршрут к `127.0.0.1` или к виртуальным свитчам Docker. Проверка: `cd scripts/rpc-smoke && npm run check`. Потом VPN можно снова включить, если без него WS заработал — значит, нужен split tunnel или исключение для Docker.
2. **Перезапуск стека:** выйти из Docker Desktop → снова запустить; в PowerShell **`wsl --shutdown`**, затем снова открыть Docker (если backend WSL2).
3. **Файрвол:** убедиться, что **Docker Desktop** не в блоке «публичные сети» без правила (иногда помогает «разрешить» для частной сети или временно отключить проверку для теста).
4. Попробовать **`ws://127.0.0.1:9944`** и **`ws://localhost:9944`** — иногда отличается (IPv4/IPv6).

#### 1) Надёжные обходы (без «лечения» Docker)

- **Запускать фронт / Node в Docker** в той же сети, что `localnet`, RPC: **`ws://localnet:9944`** — не использует проброс WS на хост.
- **Или** запускать **`npm run dev` / браузер из WSL2** и смотреть `ws://127.0.0.1:9944` оттуда — часто стабильнее, чем Win32.

#### 2) Опционально: WSS через Caddy (profile `wss`)

Отдельный контейнер слушает **`wss://127.0.0.1:3443`**, внутри сети проксирует на **`ws://localnet:9944`**. Нужен для кошельков, которые принимают только `wss://`. Локальный сертификат (`tls internal`) — см. [Caddy local HTTPS](https://caddyserver.com/docs/automatic-https#local-https). Если TLS к прокси ругается, используй п.1.

```powershell
docker compose -f docker-compose.localnet.yml --profile wss up -d
```

Файл конфига: [`support/Caddyfile.subtensor-rpc-wss`](support/Caddyfile.subtensor-rpc-wss).

### RPC smoke tests (Polkadot JS API)

From repo root:

```powershell
cd scripts/rpc-smoke
npm install
npm run check
```

This connects to **`ws://127.0.0.1:9944`**, times out after 15s if the node is down (avoids hanging like some UIs), prints chain name, head block, and **`//Alice`** free balance. To watch a few new blocks: `npm run new-heads`. Details and env vars: [`scripts/rpc-smoke/README.md`](scripts/rpc-smoke/README.md).

### TAO on local testnet

There is **no faucet**: TAO comes from **genesis**. Well-known dev accounts (`//Alice`, `//Bob`, `//Charlie`, etc.) are pre-funded (see `node/src/chain_spec/localnet.rs` — e.g. **1,000,000 TAO** for Alice/Bob/Charlie at **9 decimals**). Use `//Alice` only on local dev chains. For CLI flows, see [Provision wallets (local)](https://docs.learnbittensor.org/local-build/provision-wallets/).

**Fast blocks:** default is `command: ["True"]`. For the non-fast-blocks binary, set `command: ["False"]` on the `localnet` service.

Stop:

```powershell
docker compose -f docker-compose.localnet.yml down
```

Reset chain data (volume names depend on [Compose project name](https://docs.docker.com/compose/how-tos/project-name/); default folder name `xsubtensor`):

```powershell
docker volume rm xsubtensor_subtensor-localnet-alice xsubtensor_subtensor-localnet-bob
```

### Pin a different tag

Edit `image:` on the `localnet` service (for example `devnet-ready` if that tag exists for your needs). Use a [Compose override file](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/) if you prefer not to edit the tracked file.

### Several clones on one machine

```powershell
docker compose -p my-subtensor-local -f docker-compose.localnet.yml pull
docker compose -p my-subtensor-local -f docker-compose.localnet.yml up -d
```

## Public networks (mainnet / testnet)

[`docker-compose.yml`](docker-compose.yml) uses **`ghcr.io/opentensor/subtensor:latest-amd64`** (see [docker workflow](.github/workflows/docker.yml)). On **Apple Silicon**, switch the `image` under `common` to **`ghcr.io/opentensor/subtensor:latest-arm64`**.

**Warning:** These nodes sync real networks (disk, bandwidth, time). Run **one** service at a time so ports `9944` / `30333` / `9933` do not conflict.

```powershell
docker login ghcr.io -u YOUR_GITHUB_USERNAME
docker compose -f docker-compose.yml pull
docker compose -f docker-compose.yml up -d testnet-lite
```

Service names: `mainnet-lite`, `mainnet-archive`, `testnet-lite`, `testnet-archive`.

Stop:

```powershell
docker compose -f docker-compose.yml down
```

### Logs (mainnet / testnet compose)

Follow logs for one service, for example `testnet-lite`:

```powershell
docker compose -f docker-compose.yml logs -f testnet-lite
```

Or by container name, e.g. `subtensor-testnet-lite`:

```powershell
docker logs -f subtensor-testnet-lite
```

## What you are *not* getting

Pre-built images match **published** Opentensor tags, not arbitrary commits in your fork. To run **your** build, use `docker build` / `cargo build` and point `image:` at your own registry or local tag.

## More reading

- [SETUP_LOG_SUBNET_MATH.md](SETUP_LOG_SUBNET_MATH.md) — лог настройки `subnet-math`, submodule, диагностика WebSocket на Windows + Docker
- [SUBNET_MATH_LOCALNET.md](SUBNET_MATH_LOCALNET.md) — subnet-math на localnet: шаги вручную, `.env.subnet-math`, `btcli`, compose; **§4** — полный набор identity-флагов для `subnet create` (без залипания на prompts), фоновые `scripts/subnet-create-localnet.cmd` / `subnet-start-localnet.cmd` и логи `subnet-create.log` / `subnet-start.log`
- [SUBNET_VLA_LOCALNET.md](SUBNET_VLA_LOCALNET.md) — `subnet-vla` как robokitchen chain shim: compose, kitchen runtime, `query_miner.py`
- [SUBNET_SLAM_LOCALNET.md](SUBNET_SLAM_LOCALNET.md) — `subnet-slam` scaffold: compose, semantic-slam runtime, miner/validator shim
- [REQUEST_NET_GRAPH.md](REQUEST_NET_GRAPH.md) — JSON-RPC метаграфов/нейронов, `GET /v1/network-snapshot` (faucet), pretty-примеры [`docs/network-snapshot.example.json`](docs/network-snapshot.example.json) / [`docs/network-snapshot.full.example.json`](docs/network-snapshot.full.example.json)
- [REQUEST_TO_SUBNET.md](REQUEST_TO_SUBNET.md) — HTTP probe: dendrite MathSynapse, детальный JSON по майнерам и reward; прокси `POST /v1/subnet-math-probe` на faucet
- [SUBNET_MATH_OPERATIONS.md](SUBNET_MATH_OPERATIONS.md) — логи, `MATH_SCOREBOARD`, запрос к майнеру (`query_miner.py`), метаграф
- [docs/running-subtensor-locally.md](docs/running-subtensor-locally.md)
- [Bittensor docs — Subtensor nodes](https://docs.bittensor.com/subtensor-nodes)
- Packages: [subtensor](https://github.com/opentensor/subtensor/pkgs/container/subtensor), [subtensor-localnet](https://github.com/opentensor/subtensor/pkgs/container/subtensor-localnet)
