# Local HTTP faucet (Docker)

Опциональный сервис для **локального dev**: читает баланс **faucet-аккаунта** (по умолчанию `//Alice`) и шлёт **TAO** через `balances.transferKeepAlive`. Работает только вместе с поднятым [`docker-compose.localnet.yml`](docker-compose.localnet.yml).

**Безопасность:** в контейнере используется dev-сид `//Alice`. Не публикуйте порт в интернет и не используйте на публичных сетях.

## Запуск

Из корня репозитория:

```powershell
docker compose -f docker-compose.localnet.yml pull
docker compose -f docker-compose.localnet.yml up -d
docker compose -f docker-compose.localnet.yml --profile faucet up -d
```

Сервис слушает **`http://127.0.0.1:8090`** (только localhost).

Переменные окружения (в [`docker-compose.localnet.yml`](docker-compose.localnet.yml) у сервиса `faucet`):

| Переменная | Значение по умолчанию | Смысл |
|------------|------------------------|--------|
| `WS_URL` | `ws://localnet:9944` | WebSocket RPC ноды **внутри** Docker-сети compose |
| `FAUCET_SEED` | `//Alice` | URI кошелька, с которого подписываются переводы |
| `PORT` | `8090` | HTTP-порт внутри контейнера |
| `FAUCET_MAX_TAO_PER_TRANSFER` | `1000000` | Верхняя граница суммы одного перевода (TAO) |

## API

### `GET /health`

Проверка, что RPC доступен и цепочка отвечает.

```bash
curl.exe -sS http://127.0.0.1:8090/health
```

Пример ответа:

```json
{"ok":true,"ws":"ws://localnet:9944","head":"1234"}
```

### `GET /v1/balance`

Баланс **free** у faucet-аккаунта (`//Alice` по умолчанию).

```bash
curl.exe -sS http://127.0.0.1:8090/v1/balance
```

Пример ответа:

```json
{
  "ss58": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
  "seed_hint": "dev URI",
  "free_rao": "1000000000000000",
  "free_tao": "1000000.000000000"
}
```

`free_rao` — целое в минимальных единицах (9 знаков после запятой у TAO).

### `POST /v1/transfer`

Тело JSON (одно из полей суммы):

- **`amount_tao`** — строка с десятичной дробью, например `"0.001"`;
- **`amount_rao`** — целая строка в минимальных единицах, например `"1000000"` (= 0.001 TAO).

Поля:

- **`dest`** (обязательно) — SS58 получателя.

**Пример (bash / Git Bash)** — перевод `0.001` TAO:

```bash
curl.exe -sS -X POST http://127.0.0.1:8090/v1/transfer \
  -H "Content-Type: application/json" \
  -d "{\"dest\":\"5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty\",\"amount_tao\":\"0.001\"}"
```

**Пример (PowerShell)** — удобнее `Invoke-RestMethod`, чтобы не ломать JSON:

```powershell
Invoke-RestMethod `
  -Uri "http://127.0.0.1:8090/v1/transfer" `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"dest":"5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty","amount_tao":"0.001"}'
```

**Пример через файл** (если `curl` в PowerShell искажает JSON):

```powershell
@'
{"dest":"5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty","amount_tao":"0.001"}
'@ | Set-Content -Encoding utf8 body.json -NoNewline

curl.exe -sS -X POST http://127.0.0.1:8090/v1/transfer `
  -H "Content-Type: application/json" `
  --data-binary "@body.json"
```

Эквивалент через `amount_rao`:

```bash
curl.exe -sS -X POST http://127.0.0.1:8090/v1/transfer \
  -H "Content-Type: application/json" \
  -d "{\"dest\":\"5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty\",\"amount_rao\":\"1000000\"}"
```

Успешный ответ (идентификатор транзакции в стиле Substrate — **хэш экстринсики** + блок включения):

```json
{
  "ok": true,
  "extrinsic_hash": "0x12be5d9a52eb772d462de1d3a03f9ec1d362900ac0abeae6d57f9633cb941fa8",
  "block_hash": "0x7e87de0b609aa96f297f3a8203e5935189970082a8e053b013f4baffab7b387d",
  "block_number": 5833,
  "status": "in_block",
  "hash": "0x12be5d9a52eb772d462de1d3a03f9ec1d362900ac0abeae6d57f9633cb941fa8",
  "from": "5GrwvaEF5zXb26Fz9rcQpDWS57CtERHpNehXCPcNoHGKutQY",
  "dest": "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty",
  "amount_rao": "1000000"
}
```

- **`extrinsic_hash`** — идентификатор экстринсики (то же, что раньше было в поле `hash`; `hash` оставлено для совместимости).
- **`block_hash`** / **`block_number`** — блок, в котором транзакция **включена** (ещё не обязательно **финализирована**).
- **`status`** — сейчас всегда `in_block` (ответ отдаётся после включения в блок).

### `GET /v1/tx-status` — проверка по `block_hash` + `extrinsic_hash`

Тот же статус, что можно собрать из storage событий по RPC: найдена ли экстринсика в блоке, успешен ли dispatch, грубая подсказка по финализации.

Параметры query (оба обязательны):

- **`block_hash`** — из ответа `POST /v1/transfer`;
- **`extrinsic_hash`** — из ответа `POST /v1/transfer` (тот же, что `hash`).

```bash
curl.exe -sS "http://127.0.0.1:8090/v1/tx-status?block_hash=0xBLOCK&extrinsic_hash=0xEXT"
```

Пример ответа:

```json
{
  "extrinsic_hash": "0x12be5d9a52eb772d462de1d3a03f9ec1d362900ac0abeae6d57f9633cb941fa8",
  "block_hash": "0x7e87de0b609aa96f297f3a8203e5935189970082a8e053b013f4baffab7b387d",
  "block_number": 5833,
  "extrinsic_index": 2,
  "dispatch_success": true,
  "finalized_head_block_number": 5825,
  "finalized_hint": false
}
```

- **`dispatch_success`** — по событиям `system.ExtrinsicSuccess` / `ExtrinsicFailed` для индекса экстринсики в этом блоке.
- **`finalized_hint`** — эвристика: `finalized_head_block_number >= block_number` (на быстром localnet голова финализации может **отставать**, тогда будет `false`, пока блок не догонят — это нормально).

**PowerShell** (кавычки в URL):

```powershell
$block = "0x7e87de0b609aa96f297f3a8203e5935189970082a8e053b013f4baffab7b387d"
$ext = "0x12be5d9a52eb772d462de1d3a03f9ec1d362900ac0abeae6d57f9633cb941fa8"
Invoke-RestMethod -Uri "http://127.0.0.1:8090/v1/tx-status?block_hash=$block&extrinsic_hash=$ext"
```

## Проверка тем же JSON-RPC, что и нода (HTTP на `9944`)

С хоста нода слушает **`http://127.0.0.1:9944`** (тот же JSON-RPC, что и по WebSocket). Можно **не** ходить в faucet, а запрашивать блок и хэш финализированной головы обычными вызовами.

Подставьте **`block_hash`** из ответа перевода.

**Файл `get-block.json`:**

```json
{"jsonrpc":"2.0","id":1,"method":"chain_getBlock","params":["0xYOUR_BLOCK_HASH"]}
```

```bash
curl.exe -sS -X POST http://127.0.0.1:9944 -H "Content-Type: application/json" --data-binary "@get-block.json"
```

В `result.block.extrinsics` будут закодированные экстринсики; совпадение с вашей транзакцией проще проверять через **`extrinsic_hash`** и `GET /v1/tx-status`, чем вручную декодировать список.

**Финализированная голова цепи:**

**Файл `get-finalized-head.json`:**

```json
{"jsonrpc":"2.0","id":1,"method":"chain_getFinalizedHead","params":[]}
```

```bash
curl.exe -sS -X POST http://127.0.0.1:9944 -H "Content-Type: application/json" --data-binary "@get-finalized-head.json"
```

Дальше по `result` можно вызвать `chain_getHeader` и сравнить номер с `block_number` вашей транзакции (когда финализация догонит, номер финализированной головы станет ≥ номера блока с экстринсикой).

## Локальный запуск без Docker (разработка)

```powershell
cd services\faucet
npm install
$env:WS_URL="ws://127.0.0.1:9944"
$env:PORT="8090"
node server.mjs
```

Нода должна быть доступна по `WS_URL` с хоста (после `docker compose up -d` для `localnet`).

## Проверено

- `GET /health`, `GET /v1/balance` — ответ 200, баланс Alice согласован с genesis localnet.
- `POST /v1/transfer` — возвращает `extrinsic_hash`, `block_hash`, `block_number`, `status: in_block` и дубликат `hash`.
- `GET /v1/tx-status` — по `block_hash` + `extrinsic_hash` возвращает `dispatch_success` и индекс экстринсики.
- `curl` **POST** на `http://127.0.0.1:9944` с телом `chain_getBlock` / `chain_getFinalizedHead` — ответ 200, JSON-RPC как у ноды.
