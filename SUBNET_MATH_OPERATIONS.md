# subnet-math: запуск, запросы, награды, логи

Здесь одна страница «что запускать и что смотреть». Поднятие сабнета в цепи (кошельки, `btcli`, `NETUID`) — **только вручную по шагам** в [`SUBNET_MATH_LOCALNET.md`](SUBNET_MATH_LOCALNET.md) §4 (все identity-флаги + фоновые `scripts/subnet-create-localnet.cmd` / `subnet-start-localnet.cmd`, чтобы не залипать на prompts).

Ниже — команды **после** того, как цепь и `.env.subnet-math` уже готовы.

## 1. Запуск стека

```powershell
cd <корень-xsubtensor>

docker compose -f docker-compose.localnet.yml up -d
docker compose -f docker-compose.localnet.yml --profile faucet up -d

copy .env.subnet-math.example .env.subnet-math
# прописать NETUID и имена кошельков после btcli

docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math up -d --build
```

Проверка, что контейнеры живы:

```powershell
docker ps --filter name=subtensor-math
```

## 2. Логи

```powershell
docker logs -f subtensor-math-miner
docker logs -f subtensor-math-validator
docker logs -f subtensor-math-miner-b
docker logs -f subtensor-math-validator-b
```

Только строки скоринга валидатора:

```powershell
docker logs subtensor-math-validator 2>&1 | Select-String "MATH_SCOREBOARD"
```

`MATH_SCOREBOARD` — JSON: `expected`, `op`, `a`, `b`, `uids` (кого опросили), `responses`, **`rewards`** (доли победителей раунда по близости ответа к `expected`).

## 3. Запрос в сабнет (к майнеру по UID)

Майнер принимает **MathSynapse** (`operand_a`, `operand_b`, `op` из `+`, `-`, `*`). Запрос должен идти от **зарегистрированного** hotkey (иначе blacklist майнера).

Скрипт: [`subnet-math/scripts/query_miner.py`](subnet-math/scripts/query_miner.py). Пример **из Docker-сети** (endpoint ноды как у compose):

```powershell
docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math run --rm -T --entrypoint python math-miner `
  scripts/query_miner.py `
  --netuid <NETUID_из_.env> `
  --wallet-name <валидатор_или_любой_зарегистрированный> `
  --miner-uid <uid_майнера_в_метаграфе> `
  --subtensor.chain_endpoint ws://subtensor-localnet:9944 `
  --operand_a 6 --operand_b 7 --op "*"
```

`miner-uid` возьми из вывода метаграфа (следующий раздел).

## 4. Метаграф, веса, «награды» в цепи

Снимок incentive/stake по UID (JSON):

```powershell
docker compose -f docker-compose.subnet-math.yml run --rm -T --entrypoint python math-miner `
  scripts/inspect_metagraph.py --netuid <NETUID> --chain-endpoint ws://subtensor-localnet:9944
```

С хоста (если стоит venv с `bittensor`):

```powershell
python subnet-math/scripts/inspect_metagraph.py --netuid <NETUID> --chain-endpoint ws://127.0.0.1:9944
```

Через `btcli` (образ уже с CLI, см. `subnet-math/requirements.txt`):

```powershell
docker compose -f docker-compose.subnet-math.yml run --rm -T -e HOME=/root --entrypoint btcli math-miner `
  subnet show --netuid <NETUID> --network ws://localnet:9944 --wallet-path /root/.bittensor/wallets
```

Обзор кошелька:

```powershell
docker compose -f docker-compose.subnet-math.yml run --rm -T -e HOME=/root --entrypoint btcli math-miner `
  wallet overview --wallet-name <имя> --network ws://subtensor-localnet:9944 -p /root/.bittensor/wallets
```

- **Строки `MATH_SCOREBOARD`** — мгновенные доли раунда (кто ближе к правильному ответу).
- **Поля в метаграфе / `subnet show`** — уже агрегированные incentive/стейк в сети после того, как валидатор выставляет веса (не путать с одним раундом квиза).

## 5. Mock без цепи (только проверка кода)

```powershell
docker compose -f docker-compose.subnet-math.yml --profile mock up -d --build
docker logs -f subtensor-math-validator-mock
```

---

Файл **`.env.subnet-math`** создаёшь **локально** (`copy .env.subnet-math.example .env.subnet-math`), в git он не коммитится (см. `.gitignore`).
