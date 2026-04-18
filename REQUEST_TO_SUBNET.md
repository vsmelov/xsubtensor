# Запросы в подсети по HTTP

Один **POST** с JSON: валидаторский кошёлёк (внутри probe) делает **dendrite → axon** майнеров и возвращает сводку. Снимок цепи отдельно: [`GET /v1/network-snapshot`](REQUEST_NET_GRAPH.md).

## Куда слать

| Подсеть | Прямой URL (хост) | Через faucet `8090` |
|---------|-------------------|---------------------|
| **subnet-math** | `http://127.0.0.1:8092/v1/math-probe` | `http://127.0.0.1:8090/v1/subnet-math-probe` |
| **subnet-vla** | `http://127.0.0.1:8094/v1/vla-probe` | `http://127.0.0.1:8090/v1/subnet-vla-probe` |
| **vla-video-analyzer** (OpenAI vision, для `using_ai_verification`) | `http://127.0.0.1:8095` (`GET /health`, `POST /v1/analyze`) | — |

Заголовок: `Content-Type: application/json`. Тело — UTF-8 **без BOM** (иначе probe может не разобрать JSON).

Общие поля тела (все опциональны, часть берётся из env контейнера probe): `netuid`, `wallet_name`, `hotkey`, `chain_endpoint`, `miner_uids`, `sample_size`, `timeout`.

Поднять ноды и probe: [**SUBNET_MATH_LOCALNET.md**](SUBNET_MATH_LOCALNET.md) (math), шаблон VLA — [`.env.subnet-vla.example`](.env.subnet-vla.example) + [`docker-compose.subnet-vla.yml`](docker-compose.subnet-vla.yml).

---

## subnet-math — `MathSynapse`

**Свои поля:** `operand_a`, `operand_b`, `op` (`+`, `-`, `*`).

**Пример тела:** [`scripts/math-probe-body.example.json`](scripts/math-probe-body.example.json)

```json
{"netuid":2,"sample_size":2,"operand_a":10,"operand_b":2,"op":"*"}
```

Если не задать `miner_uids`, в выборку могут попасть **валидаторы** — у них другой axon, для `MathSynapse` часто будет `503`. Чтобы опросить только майнеров, добавьте, например: `"miner_uids": [1]`.

**Что в ответе при `ok: true`:** `protocol`, `netuid`, `chain_endpoint`, `wallet_coldkey`, `request` (включая эталон **`expected`**), массив **`miners`** (у каждого: `uid`, `response_float`, `abs_error`, `reward_share`, `synapse` с `dendrite.status_code` / `status_message`), массив **`rewards`**, **`timing_ms`**.

**Проверенный `curl`** (из корня репо, PowerShell):

```powershell
curl.exe -sS --max-time 90 -H "Content-Type: application/json" --data-binary "@scripts\math-probe-body.example.json" http://127.0.0.1:8092/v1/math-probe
```

Тот же запрос через faucet:

```powershell
curl.exe -sS --max-time 90 -H "Content-Type: application/json" --data-binary "@scripts\math-probe-body.example.json" http://127.0.0.1:8090/v1/subnet-math-probe
```

**Фрагмент реального ответа** (netuid 2, опрошены uid 1 и 2: майнер дал число, валидатор — `503`):

```json
{
  "ok": true,
  "protocol": "subnet-math MathSynapse",
  "netuid": 2,
  "request": { "operand_a": 10, "operand_b": 2, "op": "*", "expected": 20.0 },
  "miner_uids_queried": [1, 2],
  "miners": [
    {
      "uid": 1,
      "response_float": 19.994417293825975,
      "abs_error": 0.005582706174024565,
      "reward_share": 1.0,
      "synapse": {
        "result": 19.994417293825975,
        "dendrite": { "status_code": 200, "status_message": "Success" }
      }
    },
    {
      "uid": 2,
      "response_float": null,
      "abs_error": null,
      "reward_share": 0.0,
      "synapse": {
        "result": null,
        "dendrite": {
          "status_code": 503,
          "status_message": "Service unavailable at …:9101/MathSynapse"
        }
      }
    }
  ],
  "rewards": [1.0, 0.0]
}
```

---

## subnet-vla — `VLASynapse`

**Своё поле:** **`task`** — текст задачи робота. Допустимые значения: `Clean-up the guestroom`, `Clean-up the kitchen`, `Prepare groceries`, `Setup the table` (см. [`subnet-vla/template/protocol.py`](subnet-vla/template/protocol.py)).

**Пример тела:** [`scripts/vla-probe-body.example.json`](scripts/vla-probe-body.example.json)

```json
{"netuid": 3, "sample_size": 1, "miner_uids": [1], "task": "Clean-up the guestroom"}
```

**Что в ответе при `ok: true`:** как у math, но в `request` — `task` и `allowed_tasks`; у майнера вместо `response_float` — **`video_url`** (в заглушке один и тот же URL).

**ИИ-верификация видео (`using_ai_verification`):** если в теле **`"using_ai_verification": true`**, после ответов майнеров probe для **каждого** майнера с непустым `video_url` параллельно вызывает сервис **AI video analyzer** (FastAPI), который гоняет ролик через тот же пайплайн, что и [`video-robot-eval`](subnet-vla/video-robot-eval/) (кадры 0.5 с, батчи по 12, merge с `importance`, без встроенных PNG в JSON по умолчанию).

- **URL анализатора:** поле тела **`video_analyzer_url`** (строка), иначе переменная окружения контейнера probe **`VLA_VIDEO_ANALYZER_URL`**. В `docker-compose.subnet-vla.yml` по умолчанию для контейнера probe: `http://vla-video-analyzer:8000`; с хоста напрямую к анализатору: `http://127.0.0.1:8095` (`GET /health`, `POST /v1/analyze` с JSON `video_url`, опционально `task`, `embed_png`, `fps`, `frames_per_batch`).
- **Ключ OpenAI** задаётся для сервиса **`vla-video-analyzer`** (`OPENAI_API_KEY` в `.env.subnet-vla`), не для probe.
- В ответе probe при успехе: на верхнем уровне **`using_ai_verification`: true**, **`video_analyzer_url`**; у каждого элемента **`miners`** — объект **`ai_verification`**: при успехе `{ "ok": true, "analysis": { ... } }` (внутри `analysis` те же поля, что в отчёте `video-robot-eval`: **`predicted_task_prompt`** — краткая гипотеза, какую инструкцию давали VLA под это видео, плюс `evaluation`, `usage`, `estimated_usd`, …); при ошибке `{ "ok": false, "error": "..." }`.
- **`OPENAI_API_KEY`** для `vla-video-analyzer`: в compose подключаются **`env_file`** `.env.subnet-vla` и **`subnet-vla/video-robot-eval/.env`** (достаточно ключа в одном из файлов; приоритет у переменных из **последнего** файла в списке — `subnet-vla/video-robot-eval/.env`).

Если включили флаг, но не задали URL и не настроили `VLA_VIDEO_ANALYZER_URL`, вернётся **`ok: false`** с текстом ошибки (при этом список **`miners`** с ответами сети может быть прислан для отладки).

**Проверенный `curl`:**

```powershell
curl.exe -sS --max-time 90 -H "Content-Type: application/json" --data-binary "@scripts\vla-probe-body.example.json" http://127.0.0.1:8094/v1/vla-probe
```

Через faucet:

```powershell
curl.exe -sS --max-time 90 -H "Content-Type: application/json" --data-binary "@scripts\vla-probe-body.example.json" http://127.0.0.1:8090/v1/subnet-vla-probe
```

**Фрагмент реального ответа** (netuid 3, один майнер uid 1):

```json
{
  "ok": true,
  "protocol": "subnet-vla VLASynapse",
  "netuid": 3,
  "request": {
    "task": "Clean-up the guestroom",
    "allowed_tasks": [
      "Clean-up the guestroom",
      "Clean-up the kitchen",
      "Prepare groceries",
      "Setup the table"
    ]
  },
  "miner_uids_queried": [1],
  "miners": [
    {
      "uid": 1,
      "video_url": "https://konnex-ai.xyz/videos/results_tidy/40.mp4",
      "reward_share": 1.0,
      "synapse": {
        "video_url": "https://konnex-ai.xyz/videos/results_tidy/40.mp4",
        "task": "Clean-up the guestroom",
        "dendrite": { "status_code": 200, "status_message": "Success" }
      }
    }
  ],
  "rewards": [1.0]
}
```

**Пример тела с ИИ-верификацией** (тот же probe, после поднятия `vla-video-analyzer` и `OPENAI_API_KEY`):

```json
{
  "netuid": 3,
  "sample_size": 2,
  "miner_uids": [1, 2],
  "task": "Clean-up the guestroom",
  "using_ai_verification": true,
  "timeout": 300
}
```

---

## Заметки

- У каждой подсети свой путь и свой synapse; тела взаимно не подменяются.
- Это один синтетический опрос, а не полный лог валидатора в реальном времени.

Код: math — [`subnet-math/scripts/subnet_probe_http.py`](subnet-math/scripts/subnet_probe_http.py); vla — [`subnet-vla/scripts/vla_probe_http.py`](subnet-vla/scripts/vla_probe_http.py).
