# Лог действий: submodule `subnet-math`, арифметика, проверка тестнета

Подробная хронология того, что было сделано в репозитории `xsubtensor`, и как этим пользоваться.

---

## 1. Проверка «жив ли тестнет»

### 1.1. Docker

Выполнено: `docker ps`.

**Результат:** контейнер `subtensor-localnet` в статусе **Up**, порты проброшены: `9944–9945`, `30334–30335`.

**Вывод:** процессы нод внутри контейнера работают (логи показывают импорт блоков #5156+).

### 1.2. TCP с хоста Windows

Выполнено: `Test-NetConnection 127.0.0.1 -Port 9944`.

**Результат:** `TcpTestSucceeded : True`.

**Вывод:** до порта на localhost с хоста достучаться можно на уровне TCP.

### 1.3. WebSocket + Polkadot API с хоста Windows

Выполнено: `cd scripts/rpc-smoke && node check.mjs` (endpoint по умолчанию `ws://127.0.0.1:9944`).

**Результат:** повторяющиеся сообщения `API-WS: disconnected ... 1006:: Abnormal Closure`, затем таймаут `ApiPromise.create`.

**Вывод:** **цепочка не «мёртвая»**, но **поднятие полноценного WebSocket RPC с хоста Windows на опубликованный порт Docker Desktop часто ломается** (типичный симптом — `1006` / `socket hang up` в браузере и в Node). Это совпадает с вашим скрином Konnex (Chrome + `@polkadot/api`).

### 1.4. WebSocket из другого контейнера в той же Docker-сети

Сеть compose-проекта: **`xsubtensor_default`** (из `docker inspect subtensor-localnet`).

Выполнено (смысл команды):

- Запущен одноразовый контейнер `node:22-alpine` с сетью **`--network xsubtensor_default`**.
- Смонтирован каталог `scripts/rpc-smoke`, установлен пакет `ws`, выполнен скрипт подключения к **`ws://subtensor-localnet:9944`**.

**Результат:** в логе **`OPEN ws://subtensor-localnet:9944`**, затем закрытие с кодом **1005** после `close()` (нормально для теста).

**Вывод:** **JSON-RPC over WebSocket на ноде работает**; клиент должен ходить на **`ws://subtensor-localnet:9944` из той же docker-сети**, а не обязательно с Windows-хоста на `127.0.0.1:9944`.

### 1.5. Вспомогательный файл для повторения проверки

Добавлен: [`scripts/rpc-smoke/ws-docker-probe.mjs`](scripts/rpc-smoke/ws-docker-probe.mjs).

Пример команды (PowerShell, пути поправьте при необходимости):

```powershell
docker run --rm --network xsubtensor_default -v "${PWD}/scripts/rpc-smoke:/app" -w /app node:22-alpine sh -c "npm i ws@8 --silent && node ws-docker-probe.mjs"
```

Ожидание: строка `OPEN ws://subtensor-localnet:9944`.

---

## 2. Что делать с фронтендом (Konnex на `localhost:5173`)

| Вариант | Идея |
| ------- | ---- |
| **A. Фронт в Docker** | Собрать/запустить Vite/React в сервисе в том же `docker-compose` (или `network: xsubtensor_default`), в env указать `VITE_WS=ws://subtensor-localnet:9944`. |
| **B. WSL2** | Запускать `npm run dev` из WSL и открывать сайт из WSL; иногда проброс `localhost` ведёт себя иначе, чем чистый Win32. |
| **C. VPN / фильтры** | Временно отключить VPN (NordLynx и т.д.) и проверить снова — маршрутизация может ломать даже TCP/WS к Docker. |
| **D. Обходной RPC** | Поднять отдельный прокси (редко нужно, если сработал вариант A). |

Практичнее всего для разработки — **A**: один compose-проект: `localnet` + `frontend`.

---

## 3. Git submodule `subnet-math`

### 3.1. Команда

Из корня `xsubtensor`:

```bash
git submodule add https://github.com/opentensor/subnet-template.git subnet-math
```

### 3.2. Результат

- Появился каталог **`subnet-math/`** с исходным шаблоном.
- Создан/обновлён **`.gitmodules`** с записью `path = subnet-math`, `url = https://github.com/opentensor/subnet-template.git`.
- Submodule изначально указывает на коммит **upstream** `subnet-template`.

### 3.3. Локальные правки поверх шаблона

В **`subnet-math`** заменена логика **Dummy** на **`MathSynapse`**:

- **`protocol.py`** — поля `operand_a`, `operand_b`, `op` (`+|-*`), `result`.
- **`miner.py`** — forward `solve_math`: безопасное вычисление через `operator.add/sub/mul` (без `eval`).
- **`validator.py`** — случайный пример, эталонный ответ, скоринг 0/1, прежняя схема `moving_avg` и `set_weights`.
- **`requirements.txt`**, **`README.md`** (описание на русском).

### 3.4. Фиксация коммита внутри submodule

После правок **обязательно** в submodule:

```bash
cd subnet-math
git add protocol.py miner.py validator.py requirements.txt README.md
git commit -m "feat: MathSynapse arithmetic miner/validator (fork of template)"
```

Затем в **корне** `xsubtensor`:

```bash
git add subnet-math
git commit -m "chore: bump subnet-math submodule to arithmetic template"
```

Так родительский репозиторий запоминает **конкретный SHA** submodule с вашими изменениями.

### 3.5. Важно: SHA submodule и `git clone`

URL в `.gitmodules` по-прежнему указывает на **`github.com/opentensor/subnet-template`**. Коммит с арифметикой существует **только у вас локально**, пока вы его **не запушили** ни в один удалённый репозиторий.

- Для **себя** на этой машине всё согласовано: родительский `xsubtensor` ссылается на локальный SHA.
- Для **другой машины** или CI после `git clone` + `git submodule update`: Git попытается получить тот же SHA с GitHub Opentensor — его там **нет** → ошибка checkout submodule.

**Что сделать перед пушем `xsubtensor` на GitHub:**

1. Создать форк **`subnet-template`** (или пустой репо) у себя, например `github.com/vsmelov/subnet-math`.  
2. В каталоге `subnet-math`: `git remote add mine https://github.com/vsmelov/subnet-math.git` и `git push mine main` (или `git remote set-url origin …` и `git push -u origin main`).  
3. В **корне** `xsubtensor` отредактировать `.gitmodules`: `url = …/vsmelov/subnet-math.git`, затем `git submodule sync` и закоммитить изменение `.gitmodules`.

Либо **отказаться от submodule** и держать код как обычную папку в `xsubtensor` (без отдельного репо) — тогда один пуш родителя достаточен.

---

## 4. Дальнейшие шаги для вас (сабнет + 1 майнер + 1 валидатор)

Кратко (детали — [`SUBNET_MATH_LOCALNET.md`](SUBNET_MATH_LOCALNET.md)):

1. Локальный Subtensor уже из [`RUN_LOCAL.md`](RUN_LOCAL.md).
2. Кошельки: создатель сабнета, майнер, валидатор; пополнение с `//Alice`.
3. Неинтерактивное `btcli subnet create` (все поля identity + `--no-prompt`) и `subnet start` — см. [**SUBNET_MATH_LOCALNET.md**](SUBNET_MATH_LOCALNET.md) §4 и скрипты `scripts/subnet-create-localnet.cmd` / `subnet-start-localnet.cmd`.
4. `btcli subnets register` для майнера и валидатора на этот `netuid`.
5. `btcli stake add` на валидатор (validator permit).
6. В **`subnet-math`**: venv, `pip install -r requirements.txt`.
7. Запуск:
   - майнер: `python miner.py --netuid NETUID --subtensor.network local --wallet.name … --wallet.hotkey … --axon.port 8901`
   - валидатор: `python validator.py --netuid NETUID --subtensor.network local --wallet.name … --wallet.hotkey …`

Если **Python** тоже должен ходить в цепочку **с Windows-хоста** и снова получаете `1006`, запускайте майнер/валидатор **в контейнере** с сетью `xsubtensor_default` и укажите endpoint **`ws://subtensor-localnet:9944`** (через переменные окружения / флаги вашей версии `bittensor`, например `SUBTENSOR_CHAIN_ENDPOINT` — уточните в доке вашей версии SDK).

---

## 5. Сводка

| Вопрос | Ответ |
| ------ | ----- |
| Жива ли цепь? | Да, блоки идут в `docker logs subtensor-localnet`. |
| Работает ли WS RPC? | **Да, из контейнера** в сети `xsubtensor_default` на `subtensor-localnet:9944`. |
| Почему падает фронт с Win? | Очень похоже на **ограничение проброса WS через Docker Desktop (Windows)**, а не на «нода не запущена». |
| Где код «арифметики»? | Каталог **`subnet-math/`** (submodule от `subnet-template` + коммит с `MathSynapse`). |

---

## 6. Ссылки

- [subnet-template (upstream)](https://github.com/opentensor/subnet-template)
- [RUN_LOCAL.md](RUN_LOCAL.md)
- [RUN_LOCAL_SUBNET.md](RUN_LOCAL_SUBNET.md)
- [scripts/rpc-smoke/README.md](scripts/rpc-smoke/README.md)
