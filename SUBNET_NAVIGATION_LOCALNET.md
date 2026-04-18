# subnet-navigation (localnet)

Copy of **subnet-math** in `subnet-navigation/`. Compose **subnet-navigation**: 2 miners (8933/8934), 2 validators (9133/9134), probe **http://127.0.0.1:8096**.

1. `copy .env.subnet-navigation.example .env.subnet-navigation` — потом выставить **NETUID**.
2. Кошелёк **nav-owner** + кран + `btcli subnet create` (как в `scripts/subnet-create-navigation-localnet.cmd` / по аналогии с SUBNET_MATH_LOCALNET.md).
2b. **`btcli subnet start`** для этого netuid (владелец), иначе в доле minting сабнет будет **0%** — см. `scripts/subnet-start-navigation-localnet.cmd` или `MINTING_SHARE_SUBNETS.md`.
3. Кошельки **nav-miner**, **nav-miner-b**, **nav-val**, **nav-val-b** — кран, `btcli subnets register --netuid <N>`, для валидаторов `btcli stake add`.
4. `docker compose -f docker-compose.subnet-navigation.yml --env-file .env.subnet-navigation up -d --build`

В образе тот же `POST /v1/math-probe`, что у math.
