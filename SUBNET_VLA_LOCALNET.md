# subnet-vla (robokitchen chain shim)

`subnet-vla` больше не рассматривается как чистая demo-заглушка. В localnet он работает как chain-facing shim поверх kitchen runtime из `../kitchen-roboarm/services/task-api`.

1. `cp .env.subnet-vla.example .env.subnet-vla` и выставить `NETUID`.
2. Убедиться, что `docker compose -f docker-compose.localnet.yml up -d` уже поднял chain.
3. Поднять shim и runtime:

```bash
docker compose -f docker-compose.subnet-vla.yml --env-file .env.subnet-vla up -d --build
```

4. Проверить runtime:

```bash
curl http://127.0.0.1:${KITCHEN_RUNTIME_HOST_PORT:-8097}/healthz
```

5. Проверить chain shim:

```bash
docker compose -f docker-compose.subnet-vla.yml --env-file .env.subnet-vla run --rm -T --entrypoint python vla-miner scripts/query_miner.py --netuid "$NETUID" --wallet-name "${VALIDATOR_WALLET:-vla-val}" --miner-uid 1 --subtensor.chain_endpoint ws://subtensor-localnet:9944 --task-type CloseDrawer
```

Новый contract path:

- chain-facing `VLASynapse` использует `task_type`, `scene_id`, `layout_id`, `style_id`, `deadline_ms`, `validator_nonce`
- canonical verifier/scoring authority остаётся у kitchen runtime
- старое поле `task` сохранено только для compat/debug path
