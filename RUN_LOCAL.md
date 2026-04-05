# Running Subtensor locally (pre-built images only)

This repository’s Compose files are set up so you can run nodes **without compiling Rust**. Images are pulled from GitHub Container Registry (`ghcr.io/opentensor/subtensor`).

## Requirements

- [Docker](https://docs.docker.com/get-docker/) with Compose v2 (Docker Desktop includes it).
- Public images do not require `docker login` for `ghcr.io`. If a package is ever made private, run `docker login ghcr.io` first.

## Local testnet (two validators)

Uses [`docker-compose.localnet.yml`](docker-compose.localnet.yml). Alice and Bob both use **`ghcr.io/opentensor/subtensor:latest-local`**.

```powershell
cd <path-to-this-repo>

docker compose -f docker-compose.localnet.yml pull
docker compose -f docker-compose.localnet.yml up -d
```

- **Alice** — WebSocket/RPC on host `9944`, p2p `30334`.
- **Bob** — `9945`, p2p `30335`.

Example endpoint for tools/SDKs: `ws://127.0.0.1:9944` (or `9945`). Well-known sudo account: `//Alice`.

Stop and remove containers (named volumes keep chain data until you remove them):

```powershell
docker compose -f docker-compose.localnet.yml down
```

To reset chain state for localnet, remove the volumes (names depend on [Compose project name](https://docs.docker.com/compose/how-tos/project-name/); default is the directory name):

```powershell
docker volume rm xsubtensor_subtensor-alice xsubtensor_subtensor-bob
```

Adjust the `xsubtensor_` prefix if you use `docker compose -p myproject`.

### Pin a different image tag

Edit the `image:` line under `common` in `docker-compose.localnet.yml`, or add a [Compose override file](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/) that sets `image:` for the services you use.

To avoid clashes between several clones, use an explicit project name:

```powershell
docker compose -p my-subtensor-local -f docker-compose.localnet.yml pull
docker compose -p my-subtensor-local -f docker-compose.localnet.yml up -d
```

## Public networks (mainnet / testnet)

[`docker-compose.yml`](docker-compose.yml) defines **lite** and **archive** profiles for Finney (mainnet) and test Finney. They use **`ghcr.io/opentensor/subtensor:latest`** (production-style image, not `latest-local`).

**Warning:** These nodes sync real networks. They need disk, bandwidth, and time. Prefer **one** service at a time so ports `9944` / `30333` / `9933` do not conflict.

Pull the image, then start a single service, for example testnet lite:

```powershell
docker compose -f docker-compose.yml pull
docker compose -f docker-compose.yml up -d testnet-lite
```

Other service names: `mainnet-lite`, `mainnet-archive`, `testnet-lite`, `testnet-archive`.

Stop:

```powershell
docker compose -f docker-compose.yml down
```

## What you are *not* getting

Pre-built images match **published** Opentensor tags, not uncommitted or arbitrary commits in your fork. To run **your** compiled code, build an image locally or publish one to a registry and point `image:` at it.

## More reading

- [docs/running-subtensor-locally.md](docs/running-subtensor-locally.md) (includes a small Python check against a local RPC).
- [Bittensor docs — Subtensor nodes](https://docs.bittensor.com/subtensor-nodes).
