# subnet-navigation (localnet)

`subnet-navigation` is a chain-facing shim from the chain/metagraph side into `navigation-runtime`.

Current state:

- validators send `NavigationSynapse`;
- miners return navigation proposals, using `navigation-runtime /internal/mine` when configured;
- validators and probe score those proposals through `navigation-runtime /internal/verify-round`;
- old scalar math fields remain only as a compatibility input, not as the primary execution path.

Compose **subnet-navigation**: 2 miners (8933/8934), 2 validators (9133/9134), probe **http://127.0.0.1:8096**.

1. `copy .env.subnet-navigation.example .env.subnet-navigation` — потом выставить **NETUID**.
1a. Выставить **`KONNEX_NAV_RUNTIME_BASE_URL`** на доступный `navigation-runtime`:
    - локально с runtime на host: `http://host.docker.internal:8791`
    - runtime в общей Docker-сети: `http://navigation-runtime:8791`
2. Кошелёк **nav-owner** + кран + `btcli subnet create` (как в `scripts/subnet-create-navigation-localnet.cmd` / по аналогии с SUBNET_MATH_LOCALNET.md).
2b. **`btcli subnet start`** для этого netuid (владелец), иначе в доле minting сабнет будет **0%** — см. `scripts/subnet-start-navigation-localnet.cmd` или `MINTING_SHARE_SUBNETS.md`.
3. Кошельки **nav-miner**, **nav-miner-b**, **nav-val**, **nav-val-b** — кран, `btcli subnets register --netuid <N>`, для валидаторов `btcli stake add`.
4. `docker compose -f docker-compose.subnet-navigation.yml --env-file .env.subnet-navigation up -d --build`

Probe routes from host:

- primary: `POST http://127.0.0.1:8096/v1/navigation-probe`
- compatibility alias: `POST http://127.0.0.1:8096/v1/math-probe`
- health: `GET http://127.0.0.1:8096/health`

Navigation-shaped request example:

```json
{
  "netuid": 4,
  "wallet_name": "nav-val",
  "scene_id": "localnet-dev-scene",
  "map_id": "localnet-grid",
  "goal": {
    "kind": "coordinate_2d",
    "coordinates": { "x": 6, "y": 7 },
    "instruction": "Move toward the safe checkpoint."
  },
  "constraints": {
    "max_steps": 1,
    "timeout_s": 30.0
  }
}
```

Если нужен старый совместимый запрос, можно по-прежнему передать `operand_a` / `operand_b` / `op` на `POST /v1/math-probe`, но это только compatibility alias.
