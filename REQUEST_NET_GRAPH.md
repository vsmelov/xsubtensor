# Запросы «графа сети» и HTTP-снимка (локальный Subtensor)

Нода Subtensor отдаёт **кастомные JSON-RPC методы** (см. `pallets/subtensor/rpc/src/lib.rs`): список сабнетов, все метаграфы, нейроны по `netuid` и т.д. Ответы с суффиксом `…Info` / `getNeurons*` — это **SCALE-кодированные байты** (`Vec<u8>`), их удобно декодировать через `@polkadot/api`, `bittensor` или сырым парсером типов рантайма. **Декодированный** срез метаграфов и «ленту» последних блоков можно получить одним запросом к **faucet** — см. **раздел 6** ниже. **Off-chain** запрос к майнерам subnet-math (dendrite, скоры как у валидатора) — отдельно: [**REQUEST_TO_SUBNET.md**](REQUEST_TO_SUBNET.md).

**Эндпоинт HTTP JSON-RPC:** `http://127.0.0.1:9944` (тот же порт, что и WebSocket; см. [`docker-compose.localnet.yml`](docker-compose.localnet.yml)).

**Запуск локалнета:**

```powershell
docker compose -f docker-compose.localnet.yml up -d
```

---

## 1. Общие проверки ноды

### `system_health`

```bash
curl -sS -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"system_health","params":[]}' \
  http://127.0.0.1:9944
```

### `chain_getHeader` (голова цепи)

```bash
curl -sS -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"chain_getHeader","params":[]}' \
  http://127.0.0.1:9944
```

### Список методов RPC (поиск `subnetInfo_*`, `neuronInfo_*`)

```bash
curl -sS -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"rpc_methods","params":[]}' \
  http://127.0.0.1:9944
```

---

## 2. Сабнеты и метаграфы (основа для «сетевого графа»)

Второй параметр у методов — **блок** (`Option<BlockHash>`): `null` = последний известный ноде блок.

### Все сабнеты — `subnetInfo_getSubnetsInfo`

```bash
curl -sS -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"subnetInfo_getSubnetsInfo","params":[null]}' \
  http://127.0.0.1:9944
```

### Все метаграфы — `subnetInfo_getAllMetagraphs`

```bash
curl -sS -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"subnetInfo_getAllMetagraphs","params":[null]}' \
  http://127.0.0.1:9944
```

### Метаграф одного сабнета — `subnetInfo_getMetagraph`

Подставьте нужный `netuid` (пример: `1`):

```bash
curl -sS -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"subnetInfo_getMetagraph","params":[1,null]}' \
  http://127.0.0.1:9944
```

### Дополнительно (динамическая инфа, гиперпараметры)

```bash
# Вся динамическая информация по сабнетам
curl -sS -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"subnetInfo_getAllDynamicInfo","params":[null]}' \
  http://127.0.0.1:9944

# Гиперпараметры для netuid
curl -sS -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"subnetInfo_getSubnetHyperparams","params":[1,null]}' \
  http://127.0.0.1:9944
```

---

## 3. Нейроны (майнеры/валидаторы в терминологии сабнета)

### Облегчённый список — `neuronInfo_getNeuronsLite`

```bash
curl -sS -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"neuronInfo_getNeuronsLite","params":[1,null]}' \
  http://127.0.0.1:9944
```

### Полные нейроны — `neuronInfo_getNeurons`

```bash
curl -sS -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"neuronInfo_getNeurons","params":[1,null]}' \
  http://127.0.0.1:9944
```

---

## 4. Формат ответа

- Успешный ответ: `{"jsonrpc":"2.0","id":1,"result":...}`.
- Для методов, возвращающих `Vec<u8>`, в сыром JSON от ноды часто приходит **строка `0x…`** (hex). Клиенты вроде PowerShell `Invoke-RestMethod` могут преобразовать такой результат в **массив чисел** — это те же байты.
- Чтобы получить **читаемый JSON** без ручного декода SCALE, проще использовать Python SDK, как в [`subnet-math/scripts/inspect_metagraph.py`](subnet-math/scripts/inspect_metagraph.py):

```bash
python subnet-math/scripts/inspect_metagraph.py --netuid 2 --chain-endpoint ws://127.0.0.1:9944
```

Из контейнера **`math-miner`** (сеть `xsubtensor_default`) используйте **`ws://subtensor-localnet:9944`** (см. [`docker-compose.localnet.yml`](docker-compose.localnet.yml)). Имя **`localnet`** в DNS совпадает с **сервисом** compose-проекта `xsubtensor`, не с `container_name` ноды.

---

## 5. Windows PowerShell

`curl` в PowerShell — алиас для `Invoke-WebRequest`. Используйте **`curl.exe`** и передачу JSON без искажений:

```powershell
curl.exe --% -sS -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"system_health\",\"params\":[]}" http://127.0.0.1:9944
```

Либо:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:9944" -Method Post -ContentType "application/json" `
  -Body '{"jsonrpc":"2.0","id":1,"method":"system_health","params":[]}'
```

---

## 6. Faucet: `GET /health` и `GET /v1/network-snapshot`

Профиль **faucet** поднимает Express на **`8090`** ([`services/faucet/server.mjs`](services/faucet/server.mjs)). Требуется нода и:

```powershell
docker compose -f docker-compose.localnet.yml --profile faucet build faucet   # первый раз или после смены package.json / Dockerfile
docker compose -f docker-compose.localnet.yml --profile faucet up -d faucet
```

`server.mjs` **смонтирован** с хоста (см. [`docker-compose.localnet.yml`](docker-compose.localnet.yml) → `faucet.volumes`): после правок кода достаточно **`docker compose -f docker-compose.localnet.yml --profile faucet restart faucet`** — ребилд не нужен. Node сам по себе файлы не перечитывает, поэтому без рестарта процесс останется на старой версии.

После первого `up` / `restart` подождите пару секунд перед первым `curl` (иначе пустой ответ, пока процесс не готов).

### `GET /health`

```bash
curl -sS http://127.0.0.1:8090/health
```

### `GET /v1/network-snapshot` — «explorer в одном JSON»

Один HTTP-запрос отдаёт:

| Раздел JSON | Смысл |
|-------------|--------|
| **`snapshot_query`** | Какие параметры реально применились (глубина, фильтры). |
| **`chain`**, **`sync`**, **`head`**, **`finalized`** | Состояние ноды и цепи. |
| **`subtensor`** | Агрегаты (`total_networks`, stake, issuance). |
| **`network_graph`** | Упрощённый **граф**: сабнеты + плоский список нейронов (uid, hotkey, **`validatorPermit`**, **`hasSubnetStake`**, **`likelyValidatorRole`**, axon, incentive/dividend/emission/stake). На **localnet** у стейкнутых валидаторов `validatorPermit` часто долго остаётся `false` (обновление по эпохе) — для UI используйте **`likelyValidatorRole`** или **`hasSubnetStake`**, иначе «валидаторов не видно». Рёбра axon-трафика **в цепи нет** — см. примечание в JSON. |
| **`minting_share_hint`** | Подсказка для **pie chart** доли по сабнетам. Query: **`minting_share_mode=dashboard_fallback`** (по умолчанию) — если EMA цены (`movingPrice.bits`) ещё 0, в вес входят **taoIn** и ликвидность, чтобы новый сабнет не был 0%; **`minting_share_mode=chain_ema`** — только \|movingPrice.bits\| (как у нулевого TAO в coinbase при нулевой EMA). См. [`MINTING_SHARE_SUBNETS.md`](MINTING_SHARE_SUBNETS.md). |
| **`runtime_calls`** | Полные декодированные **`getAllMetagraphs`**, **`getAllDynamicInfo`**, **`getSubnetsInfoV2`**, делегаты, стоимость регистрации сети — срез состояния сабнетов/метаграфов из runtime API за один проход. |
| **`recent_events`** | События `system.events` по последним блокам (фильтр по pallet опционален). |
| **`recent_extrinsics`** | Список **extrinsic** по последним блокам: хэш, индекс, подписант, `section.method`, аргументы (`toHuman`). |
| **`limits`** | Жёсткие потолки из env (защита от OOM / таймаутов). |

Сырой SCALE и низкоуровневые RPC — разделы **1–4** выше.

#### `curl`: максимум данных за один запрос

Параметры ниже — **верхняя граница**, которую сервер примет при **дефолтных** `SNAPSHOT_MAX_*` в [`services/faucet/server.mjs`](services/faucet/server.mjs) (без своих env). **Без** `events_filter` и `extrinsics_filter` в ленту попадают события и extrinsic **всех** pallet’ов (в пределах `events_max` / `extrinsics_max`).

```bash
curl -sS "http://127.0.0.1:8090/v1/network-snapshot?events_depth=50&events_max=500&blocks_extrinsics_depth=30&extrinsics_max=800" -o network-snapshot-max.json
```

PowerShell (из любой папки; файл создаётся в **текущей** директории):

```powershell
curl.exe -sS "http://127.0.0.1:8090/v1/network-snapshot?events_depth=50&events_max=500&blocks_extrinsics_depth=30&extrinsics_max=800" -o network-snapshot-max.json
```

Чтобы снова сузить события (например, сабтензор и балансы), добавьте в query: `&events_filter=subtensorModule,balances,system`.

#### Где на диске смотреть пример JSON со всей структурой ответа

В репозитории лежат **готовые pretty-файлы** — то же тело ответа, что отдаёт `GET /v1/network-snapshot`, только сохранённое в проект (числа и хэши зависят от момента съёмки):

| Файл | Содержание |
|------|------------|
| **`docs/network-snapshot.example.json`** | Базовый снимок (дефолтные **3** блока в `recent_*`). |
| **`docs/network-snapshot.full.example.json`** | Самый **большой** закоммиченный пример: те же разделы, увеличенная глубина блоков и фильтр pallet в `snapshot_query` (как `python scripts/save_network_snapshot.py --full`). |

**Путь в файловой системе** (подставьте свой корень клона вместо `…`):

- Относительно корня репозитория: `docs/network-snapshot.full.example.json`
- Windows: `...\xsubtensor\docs\network-snapshot.full.example.json` (например `C:\Users\<вы>\PycharmProjects\xsubtensor\docs\network-snapshot.full.example.json`)
- WSL/Linux: `.../xsubtensor/docs/network-snapshot.full.example.json`

Самый «широкий» по pallet’ам ответ на **вашей** ноде получите командой `curl` выше и откройте сохранённый `network-snapshot-max.json` в том каталоге, откуда запускали команду.

Пересборка примеров в `docs/` (из корня репо):

```bash
python scripts/save_network_snapshot.py            # базовый -> docs/network-snapshot.example.json
python scripts/save_network_snapshot.py --full       # расширенный -> docs/network-snapshot.full.example.json
```

Вручную (эквивалент расширенного режима):

```powershell
curl.exe -sS "http://127.0.0.1:8090/v1/network-snapshot?events_depth=25&events_max=500&blocks_extrinsics_depth=20&extrinsics_max=500&events_filter=subtensorModule,balances,system" -o _snap.json
python -c "import json, pathlib; p=pathlib.Path('_snap.json'); pathlib.Path('docs/network-snapshot.full.example.json').write_text(json.dumps(json.loads(p.read_text(encoding='utf-8')), indent=2, ensure_ascii=False)+'\n', encoding='utf-8')"
```

**Важно:** «вся история блокчейна» как у полноценного эксплорера (все блоки, индекс по адресам, mempool) **одним REST не получить** — нужен **индексер**. Здесь — **снимок состояния** + **хвост последних блоков** в рамках лимитов.

#### Параметры запроса (query)

| Параметр | По умолчанию | Описание |
|----------|----------------|----------|
| **`events_depth`** | `3` | Сколько последних блоков обойти для **`recent_events`**. **`0`** — не сканировать. |
| **`events_max`** | `500` (cap из env) | Максимум строк событий. |
| **`events_filter`** | — | Через запятую **section** pallet, например `subtensorModule,balances`. |
| **`events_only_subtensor`** | `0` | Если `1` / `true` — только события **`subtensorModule`**. |
| **`blocks_extrinsics_depth`** | `3` | Сколько последних блоков для **`recent_extrinsics`**. **`0`** — отключить. |
| **`extrinsics_max`** | `200` | Максимум строк extrinsic. |
| **`extrinsics_filter`** | — | Через запятую pallet для extrinsic (по `method.section`). |
| **`minting_share_mode`** | `dashboard_fallback` | Режим весов для **`minting_share_hint`**: `chain_ema` — только EMA цены; иначе — fallback с ликвидностью (см. таблицу выше). |
| **`reward_split_placeholder`** | включено | `0` или `false` — не подставлять иллюстративный split в **`reward_split_hint.for_ui`** (только расчёт из метаграфа; `min` может остаться 0). |

Потолки env в `server.mjs`: **`SNAPSHOT_MAX_EVENTS_DEPTH`**, **`SNAPSHOT_MAX_EVENTS`**, **`SNAPSHOT_MAX_BLOCKS_EXTRINSICS_DEPTH`**, **`SNAPSHOT_MAX_EXTRINSICS`**.

#### Что **не** входит в один запрос

- История **всех** блоков и поиск по хэшу/адресу (кроме **`GET /v1/tx-status`** для одной пары block+extrinsic).
- **MATH_SCOREBOARD** и прочий off-chain скоринг — только логи валидатора.
- Прямой трафик **axon / Synapse**.
- Полная матрица **весов** по всем валидаторам (в снимке — агрегаты метаграфа).

#### Про файлы в `docs/`

Примеры сняты с рабочего localnet; после `down -v` или нового сабнета числа и хэши изменятся — перегенерируйте скриптом выше.

---

## 7. Проверено (автоматический прогон)

Команды ниже выполнялись при поднятом `localnet` на `http://127.0.0.1:9944` (актуальность проверяйте у себя). Ошибка подключения означает, что нода не запущена или порт недоступен.

| Запрос | Ожидание |
|--------|----------|
| `system_health` | `result.peers`, `isSyncing`, `shouldHavePeers` |
| `chain_getHeader` | `result.number`, `result.parentHash`, … |
| `subnetInfo_getSubnetsInfo` с `params:[null]` | `result` — байты SCALE (длина зависит от сети) |
| `subnetInfo_getAllMetagraphs` с `params:[null]` | `result` — байты SCALE |
| `neuronInfo_getNeuronsLite` с `params:[1,null]` | `result` — байты SCALE (при отсутствии сабнета 1 возможна ошибка рантайма — используйте существующий `netuid`) |
| `GET http://127.0.0.1:8090/v1/network-snapshot` (faucet) | JSON с `runtime_calls.getAllMetagraphs`, `recent_*` (по умолчанию последние 3 блока); pretty-пример: `docs/network-snapshot.example.json` |

Пример фрагмента успешного ответа `system_health`:

```json
{"jsonrpc":"2.0","id":1,"result":{"peers":2,"isSyncing":false,"shouldHavePeers":false}}
```

Повторная проверка у себя:

```powershell
curl.exe --% -sS -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"system_health\",\"params\":[]}" http://127.0.0.1:9944
```
