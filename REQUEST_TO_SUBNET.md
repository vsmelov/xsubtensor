# Запрос в сабнет (subnet-math): детальный ответ майнеров и скоры

Здесь описан **off-chain** путь: тот же механизм, что у валидатора (`dendrite` → axon майнера), но один вызов по HTTP с JSON-отчётом. **On-chain** снимок по-прежнему через [`GET /v1/network-snapshot`](REQUEST_NET_GRAPH.md) (faucet + Polkadot API).

## Почему не «всё внутри faucet»

Образ **faucet** — Node.js + `@polkadot/api`. **Bittensor SDK / dendrite / подпись запросов к axon** живут в **Python** и зафиксированы в образе subnet-math. Дублировать протокол в Node нереалистично, поэтому:

1. Контейнер **`math-probe`** слушает **8091 внутри** контейнера; на **хост** проброшен **8092** (8091 на Windows часто уже занят).
2. **Faucet** проксирует на **`http://subtensor-math-probe:8091`** (имя контейнера, внутренняя сеть) — см. [`docker-compose.localnet.yml`](docker-compose.localnet.yml).

Версии в образе subnet-math (см. [`subnet-math/requirements.txt`](subnet-math/requirements.txt)):

- **bittensor[cli]==9.7.0**
- **bittensor-cli==9.7.0**
- **bittensor-drand==0.5.0**

Probe использует **тот же** стек, что `math-miner` / `math-validator`.

## Имена Docker-образов: это не баг

Compose задаёт **разные имена проектов** и **разные сервисы**:

| Префикс образа | Откуда |
|------------------|--------|
| `xsubtensor-faucet` | [`docker-compose.localnet.yml`](docker-compose.localnet.yml), `name: xsubtensor`, сервис `faucet` |
| `subnet-math-math-miner` и т.д. | [`docker-compose.subnet-math.yml`](docker-compose.subnet-math.yml), `name: subnet-math` — шаблон имени `<project>-<service>` |

Суффиксы **`math-miner-b` / `math-validator-b`** — **вторая пара** нод (другие кошельки и порты axon). Так делать нормально; при желании можно явно задать `image: myregistry/subnet-math-miner:dev` у каждого сервиса для коротких тегов.

## Поднять probe

Нужны **localnet** и сеть **`xsubtensor_default`**, зарегистрированный кошелёк валидатора (как у `math-validator`), корректный **`NETUID`** в `.env.subnet-math`.

```powershell
docker compose -f docker-compose.localnet.yml up -d
docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math up -d --build
```

Если **`math-probe` не поднимали** после добавления сервиса:

```powershell
docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math up -d math-probe
```

Проверка (**с хоста — порт 8092**):

```powershell
curl.exe -sS http://127.0.0.1:8092/health
```

## API probe (с хоста: порт **8092**)

### `POST /v1/math-probe`

Тело JSON (все поля опциональны, дефолты из env контейнера или указанные ниже):

| Поле | Смысл |
|------|--------|
| `netuid` | Сабнет (env `NETUID`) |
| `wallet_name` | Имя coldkey, **зарегистрированного** в сабсете (env `WALLET_NAME`, обычно как у валидатора) |
| `hotkey` | Имя hotkey (по умолчанию `default`) |
| `chain_endpoint` | WS RPC (в Docker: `ws://subtensor-localnet:9944`) |
| `miner_uids` | Явный список UID; если не задан — случайная выборка |
| `sample_size` | Сколько UID опросить, если `miner_uids` нет (по умолчанию 4) |
| `operand_a`, `operand_b`, `op` | Задача `MathSynapse` (`op` ∈ `+`, `-`, `*`) |
| `timeout` | Секунды на dendrite |

Ответ (успех): `ok`, `request` (в т.ч. эталон `expected`), по каждому майнеру `uid`, `hotkey_ss58`, `axon`, `response_float`, `synapse` (поля ответа + метаданные dendrite, если SDK отдал synapse), `abs_error`, `reward_share`; массив `rewards` — те же веса, что считает [`template/validator/reward.py`](subnet-math/template/validator/reward.py) (winner-take-all по близости к `expected`).

**Проверенные команды** (из корня репо; тело — [`scripts/math-probe-body.example.json`](scripts/math-probe-body.example.json), UTF-8 **без BOM**):

```powershell
curl.exe -sS --max-time 90 -H "Content-Type: application/json" --data-binary "@scripts\math-probe-body.example.json" http://127.0.0.1:8092/v1/math-probe
```

Через **faucet** (тот же JSON):

```powershell
curl.exe -sS --max-time 90 -H "Content-Type: application/json" --data-binary "@scripts\math-probe-body.example.json" http://127.0.0.1:8090/v1/subnet-math-probe
```

Если `Cannot POST /v1/subnet-math-probe` — пересоздайте faucet с compose (нужен bind-mount `server.mjs`):  
`docker compose -f docker-compose.localnet.yml --profile faucet up -d faucet --force-recreate`.

Если `curl: (52)` на 8092 — смотрите `docker logs subtensor-math-probe`; убедитесь, что контейнер **`subtensor-math-probe`** в `docker ps`. Порт **8091 на хосте** часто занят — с хоста используйте **8092**.

## Через faucet (8090)

Внутри Docker faucet ходит на `http://subtensor-math-probe:8091` (см. [`docker-compose.localnet.yml`](docker-compose.localnet.yml)).

Отключить прокси: в override задайте `SUBNET_MATH_PROBE_URL=` (пусто).

## Ограничения

- Только протокол **subnet-math / `MathSynapse`**; другие сабсеты — другой synapse и другой сервис.
- Это **не** замена полного лога валидатора (`MATH_SCOREBOARD` в логах); здесь **один** синтетический запрос и расчёт reward по шаблону.
- Несколько валидаторов на сети — у каждого свои веса; отчёт отражает **ваш** dendrite-запрос от выбранного кошелька.

## Файлы

| Путь | Назначение |
|------|------------|
| [`subnet-math/scripts/subnet_probe_lib.py`](subnet-math/scripts/subnet_probe_lib.py) | Логика dendrite + `get_rewards` |
| [`subnet-math/scripts/subnet_probe_http.py`](subnet-math/scripts/subnet_probe_http.py) | HTTP-сервер |
| [`scripts/math-probe-body.example.json`](scripts/math-probe-body.example.json) | Пример тела POST для `curl --data-binary` |
| [`docker-compose.subnet-math.yml`](docker-compose.subnet-math.yml) | Сервис `math-probe` |
