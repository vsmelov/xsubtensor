# subnet-math на localnet (вручную, с проверкой на каждом шаге)

**Никаких автоматических provision/bootstrap-скриптов** в репо не поддерживаем: они ломаются на полпути и заставляют всё переделывать. Есть только **этот текст** — идите сверху вниз; после **каждого** блока команд проверяйте результат (ответ `btcli`, JSON, `docker ps`, логи). Ошибка на шаге — чините этот шаг и продолжайте, без «запусти скрипт заново».

После того как сабнет в цепи поднят: логи, запросы к майнеру, метаграф — в [**SUBNET_MATH_OPERATIONS.md**](SUBNET_MATH_OPERATIONS.md).

Репозиторий **не** содержит готовый `.env.subnet-math` (локальные кошельки и `NETUID` — у вас на машине). В git лежит только шаблон [`.env.subnet-math.example`](.env.subnet-math.example): скопируйте его и заполните.

```powershell
cd <корень-xsubtensor>
copy .env.subnet-math.example .env.subnet-math
```

## 0. Что должно быть уже ОК

- Docker, localnet поднят: [`RUN_LOCAL.md`](RUN_LOCAL.md) (`docker compose -f docker-compose.localnet.yml up -d`).
- **Faucet** (опционально, но для выдачи TAO с `//Alice` удобно): [`FAUCET_LOCAL.md`](FAUCET_LOCAL.md) — `docker compose -f docker-compose.localnet.yml --profile faucet up -d`, проверка `Invoke-RestMethod http://127.0.0.1:8090/health`.
- Сеть Docker для subnet-math: имя обычно `xsubtensor_default` (`docker network ls`). Если другое — в `.env.subnet-math` задайте `SUBTENSOR_DOCKER_NETWORK=...`.

Образ subnet-math с `btcli` внутри (один раз или после смены `requirements.txt`):

```powershell
docker compose -f docker-compose.subnet-math.yml build math-miner
```

## 1. `btcli` без установки на хост

Все команды ниже — из **корня репо**, endpoint с хоста: `ws://127.0.0.1:9944`.  
Внутри той же Docker-сети, что и `math-miner`, нода доступна как **`ws://subtensor-localnet:9944`** (имя контейнера из [`docker-compose.localnet.yml`](docker-compose.localnet.yml)). Старые примеры с хостнеймом `localnet` могут не резолвиться — ориентируйтесь на фактическое имя контейнера (`docker ps`).

Шаблон: без TTY (`-T`), путь к кошелькам **внутри контейнера** (volume тот же, что у `math-miner` в compose: хост `~/.bittensor` → `/root/.bittensor`):

```text
docker compose -f docker-compose.subnet-math.yml run --rm -T -e HOME=/root --entrypoint btcli math-miner … -p /root/.bittensor/wallets
```

Для `wallet new-coldkey` / `new-hotkey` без вопроса про длину мнемоники добавляйте, например, `--n-words 12`.

Проверка связи с цепью (`btcli` 9.7.x — команда **`subnets list`**, не `subnet list`; `--wallet-path` для этого вызова обычно не нужен):

```powershell
docker compose -f docker-compose.subnet-math.yml run --rm -T -e HOME=/root --entrypoint btcli math-miner subnets list --network ws://subtensor-localnet:9944 --json-out
```

Должен вернуться JSON без ошибки RPC.

### Долгие `docker compose run` + `btcli` (чтобы не зависнуть в терминале)

Команды вроде `subnet create` / `subnet start` / `subnets register` могут идти **минуты**; при неполном наборе флагов процесс **встаёт на интерактивный prompt** — снаружи это выглядит как «тишина» или зависание.

**Windows — предпочтительно:** отдельный `cmd` и редирект в файл (как в [`scripts/subnet-create-localnet.cmd`](scripts/subnet-create-localnet.cmd) / [`scripts/subnet-start-localnet.cmd`](scripts/subnet-start-localnet.cmd)). Запуск в свёрнутом окне:

```powershell
Start-Process cmd.exe -ArgumentList "/c", "`"$PWD\scripts\subnet-create-localnet.cmd`"" -WindowStyle Minimized
Get-Content .\subnet-create.log -Tail 80 -Wait   # выход Ctrl+C, контейнер при этом уже в другом процессе
```

**Не полагаться на `Start-Job` в PowerShell для `docker compose`** — у фоновой job другой контекст, редирект `*>>` часто даёт «битый» UTF-16 и теряет нормальный вывод ошибок.

**PowerShell `*> file`:** потоки попадают в файл в кодировке по умолчанию; для ручного просмотра это ок, для агента надёжнее **`subnet-*.log` из `.cmd`**.

**Linux / macOS (из корня репо):**

```bash
docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math run --rm -T -e HOME=/root --entrypoint btcli math-miner … > subnet-btcli.log 2>&1 &
tail -f subnet-btcli.log
```

**Логи ноды** (параллельно, если непонятно, жива ли цепь):

```powershell
docker logs subtensor-localnet --tail 80
```

В Cursor агенту: **не** блокировать один синхронный `run` без таймаута — фон + чтение `subnet-create.log` / `subnet-start.log` / `docker logs`.

## 2. Кошельки (имена согласуйте с `.env.subnet-math`)

Минимум три роли: **создатель сабнета** (coldkey), **майнер**, **валидатор**. У каждого coldkey — hotkey `default`.

Пример имён: `math-owner`, `math-miner`, `math-val` (как в примере env для майнера/валидатора).

Создание (без пароля на dev, неинтерактивно):

```powershell
docker compose -f docker-compose.subnet-math.yml run --rm -T -e HOME=/root --entrypoint btcli math-miner wallet new-coldkey --wallet-name math-owner --no-use-password --n-words 12 --wallet-path /root/.bittensor/wallets
docker compose -f docker-compose.subnet-math.yml run --rm -T -e HOME=/root --entrypoint btcli math-miner wallet new-hotkey --wallet-name math-owner --hotkey default --n-words 12 --wallet-path /root/.bittensor/wallets

docker compose -f docker-compose.subnet-math.yml run --rm -T -e HOME=/root --entrypoint btcli math-miner wallet new-coldkey --wallet-name math-miner --no-use-password --n-words 12 --wallet-path /root/.bittensor/wallets
docker compose -f docker-compose.subnet-math.yml run --rm -T -e HOME=/root --entrypoint btcli math-miner wallet new-hotkey --wallet-name math-miner --hotkey default --n-words 12 --wallet-path /root/.bittensor/wallets

docker compose -f docker-compose.subnet-math.yml run --rm -T -e HOME=/root --entrypoint btcli math-miner wallet new-coldkey --wallet-name math-val --no-use-password --n-words 12 --wallet-path /root/.bittensor/wallets
docker compose -f docker-compose.subnet-math.yml run --rm -T -e HOME=/root --entrypoint btcli math-miner wallet new-hotkey --wallet-name math-val --hotkey default --n-words 12 --wallet-path /root/.bittensor/wallets
```

Проверка: в `%USERPROFILE%\.bittensor\wallets\<имя>\` появились файлы.

## 3. TAO на coldkey’и

Адреса coldkey (SS58) возьмите из `coldkeypub.txt` в каталоге кошелька или через `btcli wallet overview` (см. доку Bittensor).

Через faucet (с хоста), суммы с запасом под burn и регистрации:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8090/v1/transfer" -Method Post -ContentType "application/json" -Body '{"dest":"<SS58_владельца>","amount_tao":"800000"}'
```

Повторите для майнера и валидатора. Проверьте балансы в `wallet overview` по сети `ws://127.0.0.1:9944` с хоста или `ws://subtensor-localnet:9944` из контейнера `math-miner`.

## 4. Сабнет в цепи

### 4.1 Почему «залипает» даже с `--no-prompt` (`btcli` 9.7.x)

Флаг **`--no-prompt` не отключает** пошаговый ввод **subnet identity**: для каждого опционального поля, которое вы **не** передали флагом, CLI может вывести prompt (типа **Subnet URL**, **Discord handle**, …). Внешне это выглядит как зависший терминал.

**Правило:** перед `subnet create` проверьте, что в команде есть **все** строки из таблицы ниже (значения-заглушки для dev допустимы).

| Флаг | Пример значения | Если забыть |
|------|-----------------|-------------|
| `--subnet-name` | `subnet-math` | спросит имя |
| `--github-repo` | `https://github.com/opentensor/bittensor` | спросит / зависнет на identity |
| `--subnet-contact` | `dev@local.test` | спросит контакт |
| `--subnet-url` / `--url` | `https://example.com` | prompt **Subnet URL (optional)** |
| `--discord-handle` | `none` | prompt **Discord handle (optional)** |
| `--description` | `localnet-dev` | может спросить описание |
| `--additional-info` | `none` | может спросить additional info |
| `--wallet-name`, `-H` / `--hotkey`, `-p` | `math-owner`, `default`, `/root/.bittensor/wallets` | wallet prompts |
| `--network` | `ws://subtensor-localnet:9944` | не та цепь / ошибка подключения |

Проверка актуального списка опций: `docker compose … run --rm -T --entrypoint btcli math-miner subnet create --help`.

### 4.2 Создание сабнета (одна команда, без вопросов)

Из контейнера сеть ноды — **`ws://subtensor-localnet:9944`**. Добавьте `--env-file .env.subnet-math`, если пользуетесь нестандартной сетью Docker.

```powershell
docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math run --rm -T -e HOME=/root --entrypoint btcli math-miner subnet create `
  --subnet-name subnet-math `
  --wallet-name math-owner --hotkey default `
  --network ws://subtensor-localnet:9944 `
  --github-repo https://github.com/opentensor/bittensor `
  --subnet-contact dev@local.test `
  --subnet-url https://example.com `
  --discord-handle none `
  --description localnet-dev `
  --additional-info none `
  --no-prompt `
  -p /root/.bittensor/wallets
```

**Фон + лог (рекомендуется):** [`scripts/subnet-create-localnet.cmd`](scripts/subnet-create-localnet.cmd) перезаписывает **`subnet-create.log`** в корне репо.

```powershell
Set-Location <корень-xsubtensor>
Start-Process cmd.exe -ArgumentList "/c", "`"$PWD\scripts\subnet-create-localnet.cmd`"" -WindowStyle Minimized
Get-Content .\subnet-create.log -Tail 50 -Wait
```

**Успех:** в логе строка вида `Registered subnetwork with netuid: <N>`. Ошибка сети / кошелька — тоже в этом файле.

### 4.3 Пересоздание: localnet с нуля или второй сабнет

- **Сбросили volume / пересоздали localnet** — счётчик сабнетов начинается заново; после нового `subnet create` снова смотрите **`netuid`** в `subnet-create.log` или `subnets list`, обновите **`.env.subnet-math`**.
- **Тот же localnet, второй сабнет** — смените **`--subnet-name`**, снова запишите новый **`netuid`**.
- Скрипт [`subnet-create-localnet.cmd`](scripts/subnet-create-localnet.cmd) зашивает имя `subnet-math`; для другого имени скопируйте файл локально или вызовите `docker compose …` вручную с другим `--subnet-name`.

### 4.4 Список сабнетов и `NETUID`

```powershell
docker compose -f docker-compose.subnet-math.yml run --rm -T -e HOME=/root --entrypoint btcli math-miner subnets list --network ws://subtensor-localnet:9944 --json-out
```

Запишите актуальный **`NETUID`** в **`.env.subnet-math`**.

### 4.5 Запуск эмиссий (`subnet start`)

Владелец сабнета (`math-owner`):

```powershell
docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math run --rm -T -e HOME=/root --entrypoint btcli math-miner subnet start --netuid <NETUID> --wallet-name math-owner --hotkey default --network ws://subtensor-localnet:9944 --no-prompt -p /root/.bittensor/wallets
```

**Фон + лог:** [`scripts/subnet-start-localnet.cmd`](scripts/subnet-start-localnet.cmd) пишет в **`subnet-start.log`**. Перед запуском задайте переменную окружения **`SUBNET_LOCALNET_NETUID`** (то же число, что в `.env.subnet-math`):

```powershell
$env:SUBNET_LOCALNET_NETUID = "2"   # подставьте свой netuid
Start-Process cmd.exe -ArgumentList "/c", "`"$PWD\scripts\subnet-start-localnet.cmd`"" -WindowStyle Minimized
Get-Content .\subnet-start.log -Tail 40 -Wait
```

## 5. Регистрация и стейк валидатора

Подставьте тот же `<NETUID>`, что в `.env.subnet-math`. Команды тоже могут идти долго — при необходимости тот же приём: `cmd /c "… > register-miner.log 2>&1"` или отдельное окно.

```powershell
docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math run --rm -T -e HOME=/root --entrypoint btcli math-miner subnets register --netuid <NETUID> --wallet-name math-miner --hotkey default --network ws://subtensor-localnet:9944 --no-prompt -p /root/.bittensor/wallets

docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math run --rm -T -e HOME=/root --entrypoint btcli math-miner subnets register --netuid <NETUID> --wallet-name math-val --hotkey default --network ws://subtensor-localnet:9944 --no-prompt -p /root/.bittensor/wallets

docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math run --rm -T -e HOME=/root --entrypoint btcli math-miner stake add --amount 50000 --netuid <NETUID> --wallet-name math-val --hotkey default --network ws://subtensor-localnet:9944 --no-prompt --unsafe -p /root/.bittensor/wallets
```

Проверка: `subnet show` / `wallet overview` для вашей версии `btcli`.

## 6. Запуск майнера и валидатора (Docker)

В `.env.subnet-math` должны совпадать `NETUID`, `MINER_WALLET`, `VALIDATOR_WALLET` с тем, что вы использовали в `btcli`.

```powershell
docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math up -d --build
```

**Вторая пара нод** (`math-miner-b` / `math-validator-b`, порты **8902** / **9102**): заведите cold/hotkey с именами из `MINER_WALLET_B` / `VALIDATOR_WALLET_B`, пополните coldkey через faucet, затем на том же `NETUID` выполните `subnets register` для обоих и **`stake add`** для второго валидатора (как в §5 для первого). После этого `up -d` поднимет четыре контейнера.

Логи:

```powershell
docker logs -f subtensor-math-validator
docker logs -f subtensor-math-miner
docker logs -f subtensor-math-validator-b
docker logs -f subtensor-math-miner-b
```

Ожидаемые строки со скорингом: см. [`scripts/subnet-math-status/README.md`](scripts/subnet-math-status/README.md) (`MATH_SCOREBOARD`).

## Офлайн-smoke без цепи

Только проверка кода/образа: `docker compose -f docker-compose.subnet-math.yml --profile mock up -d --build` (см. комментарии в [`docker-compose.subnet-math.yml`](docker-compose.subnet-math.yml)).
