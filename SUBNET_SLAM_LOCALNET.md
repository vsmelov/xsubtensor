# subnet-slam (semantic-slam scaffold)

`subnet-slam` добавляет в `xsubtensor` минимальный chain shim для `semantic-slam` beta-контракта.

1. `cp .env.subnet-slam.example .env.subnet-slam` и выставить `NETUID`.
2. Убедиться, что локальная chain уже поднята через `docker compose -f docker-compose.localnet.yml up -d`.
3. Поднять runtime + shim:

```bash
docker compose -f docker-compose.subnet-slam.yml --env-file .env.subnet-slam up -d --build
```

4. Проверить runtime:

```bash
curl http://127.0.0.1:${SLAM_RUNTIME_HOST_PORT:-8793}/healthz
```

5. Проверить miner path:

```bash
docker compose -f docker-compose.subnet-slam.yml --env-file .env.subnet-slam run --rm -T --entrypoint python slam-miner scripts/query_miner.py --netuid "$NETUID" --wallet-name "${VALIDATOR_WALLET:-slam-val}" --miner-uid 1 --subtensor.chain_endpoint ws://subtensor-localnet:9944 --source-type stray
```

Scaffold scope:

- `subnet-slam/template/protocol.py` — `SlamJobSynapse`
- `subnet-slam/neurons/*` — chain-facing miner / validator shim
- `docker-compose.subnet-slam.yml` — local runtime + miner/validator containers
- `subnet-slam/tests/` — reward/runtime scaffold tests
