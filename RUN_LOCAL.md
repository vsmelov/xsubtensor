# Running Subtensor locally (pre-built images only)

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

Uses [`docker-compose.localnet.yml`](docker-compose.localnet.yml). Image: **`ghcr.io/opentensor/subtensor-localnet:latest`** (published by [docker-localnet workflow](.github/workflows/docker-localnet.yml)). The container runs [`scripts/localnet.sh`](scripts/localnet.sh) with prebuilt binaries — same RPC ports as before.

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

- [docs/running-subtensor-locally.md](docs/running-subtensor-locally.md)
- [Bittensor docs — Subtensor nodes](https://docs.bittensor.com/subtensor-nodes)
- Packages: [subtensor](https://github.com/opentensor/subtensor/pkgs/container/subtensor), [subtensor-localnet](https://github.com/opentensor/subtensor/pkgs/container/subtensor-localnet)
