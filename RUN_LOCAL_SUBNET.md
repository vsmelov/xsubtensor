# Локальный сабнет, майнер и валидатор (Bittensor)

Здесь связаны воедино **Subtensor** (цепочка из этого репозитория) и **прикладной код сабнета** (Python: майнер/валидатор, обычно из официального шаблона). Цель — поднять **один пользовательский сабнет** с **одним майнером** и **одним валидатором** на своей машине, в том числе как старт к сабнету под **LLM text-to-text**.

> Официальные туториалы (тот же сценарий, больше деталей): [локальный деплой](https://docs.bittensor.com/local-build/deploy), [кошельки](https://docs.bittensor.com/local-build/provision-wallets), [создание сабнета локально](https://docs.bittensor.com/local-build/create-subnet), [майнинг и валидация на localnet](https://docs.bittensor.com/local-build/mine-validate).

## Согласованность версий (xsubtensor / нода ↔ Python)

Здесь смешиваются **две разные «версии»**, их нельзя путать:

| Что | Где живёт | Что означает |
| --- | --- | --- |
| **Subtensor (нода)** | Этот репозиторий `xsubtensor`, Docker `ghcr.io/.../subtensor-localnet`, бинарник в контейнере | Версия **runtime** Substrate / паллет; доступ снаружи — **WebSocket RPC** (`ws://127.0.0.1:9944`). |
| **Bittensor SDK + `btcli`** | `pip install bittensor` (и CLI из того же стека, см. [installation](https://docs.bittensor.com/getting-started/installation)) | **Python-клиент** к той же цепочке по RPC. Его нужно держать в **одной мажорной линии** с тем, что описано в актуальной доке Bittensor (сейчас это ветка **10.x**). |

**Почему раньше было «не консистентно»:** в субмодуле `subnet-math` в `requirements.txt` по ошибке **не было строки `bittensor`** (остались только вспомогательные пакеты вроде `torch` / `pytest`). Шаблон Opentensor задаёт зависимость явно — см. [`subnet-template/requirements.txt`](https://github.com/opentensor/subnet-template/blob/main/requirements.txt). Без этого виртуальное окружение могло тянуть **случайную** версию SDK или вообще обходиться без неё, пока вы не установите пакет вручную — отсюда расхождение с нодой и с `btcli`.

**Практическое правило:** после `git submodule update` в каталоге `subnet-math` выполните `pip install -r requirements.txt` (или `pip install -e .`) и убедитесь, что `python -c "import bittensor as bt; print(bt.__version__)"` показывает **10.x**, в одной линии с вашим `btcli`. Микропатчи (`10.2.0` vs `10.2.1`) обычно совместимы с одной и той же localnet-нодой; **переход 9.x ↔ 10.x** — уже ломает API вызовов к цепочке.

## Как устроены части системы

| Компонент | Роль |
| --------- | ---- |
| **Subtensor** (Docker `docker-compose.localnet.yml` в этом репо) | Блокчейн: сабнеты, регистрации, стейки, веса, эмиссии. |
| **`btcli`** | CLI: создать сабнет, зарегистрировать нейроны, застейкать, смотреть состояние. |
| **`subnet-template`** ([opentensor/subnet-template](https://github.com/opentensor/subnet-template)) | Минимальный **Python**: майнер + валидатор + `protocol.py`; заглушку меняете на свою задачу (например LLM). |
| **Bittensor SDK** (`pip install bittensor`) | Библиотека для связи майнера/валидатора с цепочкой и Axon. |

Subtensor **не** запускает вашу LLM. **Майнер** отдаёт модель; **валидатор** опрашивает майнеров и **выставляет веса** в сети по вашей логике скоринга.

## Что нужно заранее

1. **Локальная цепочка запущена** — см. [`RUN_LOCAL.md`](RUN_LOCAL.md) (`docker compose … up -d`).  
2. **Доступен WebSocket RPC** — например `ws://127.0.0.1:9944` (Alice) или `ws://127.0.0.1:9945` (Bob); это одна и та же логическая цепь. Быстрая проверка: [`scripts/rpc-smoke`](scripts/rpc-smoke/README.md) (`npm run check`).  
3. Установлен **`btcli`** и он в `PATH` (идёт в составе актуального стека Bittensor; см. [установку](https://docs.bittensor.com/getting-started/installation)).  
4. **Python 3.10+** для репозитория сабнета.  
5. **Кошельки** — по смыслу три роли: **владелец/создатель сабнета**, **майнер**, **валидатор** (в доках часто `sn-creator`, `test-miner`, `test-validator`). Coldkey/hotkey создаются через `btcli wallet create`, как в [provision wallets](https://docs.bittensor.com/local-build/provision-wallets).  
6. **TAO у создателя и у майнера/валидатора** — пополнить с дев-аккаунта `//Alice` (см. [`RUN_LOCAL.md`](RUN_LOCAL.md) и балансы в `node/src/chain_spec/localnet.rs`). Создание сабнета стоит **динамического burn/lock**; запаситесь TAO на регистрации и стейк валидатора.

### Fast blocks (по умолчанию в Docker localnet)

В официальной доке для режима **fast blocks** к ряду команд `btcli` рекомендуют **`--no-mev-protection`**. Добавьте флаг, если ваша версия `btcli` его поддерживает и вы видите связанные ошибки.

### Один и тот же URL WebSocket везде

Выберите один endpoint и используйте его во всех вызовах `btcli`, например:

```text
ws://127.0.0.1:9944
```

В некоторых гайдах указан `9945`; оба подойдут, если в compose проброшены оба порта (см. `docker-compose.localnet.yml`).

## Шаг 1 — Создать сабнет в цепочке

От имени кошелька **создателя** (подставьте свои имена и URL):

```powershell
btcli subnet create --subnet-name my-llm-subnet --wallet.name sn-creator --wallet.hotkey default --network ws://127.0.0.1:9944
```

Подтвердите запрос на burn/lock. Посмотрите список сабнетов и запомните новый **netuid**:

```powershell
btcli subnet list --network ws://127.0.0.1:9944
```

## Шаг 2 — Запустить эмиссии

Подставьте вместо `NETUID` идентификатор вашего сабнета:

```powershell
btcli subnet start --netuid NETUID --wallet.name sn-creator --network ws://127.0.0.1:9944
```

Без этого не будет обычного поведения эмиссий/стейкинга из [доки create-subnet](https://docs.bittensor.com/local-build/create-subnet).

## Шаг 3 — Зарегистрировать hotkey майнера и валидатора

Зарегистрируйте **каждый** hotkey на **вашем** `NETUID`:

```powershell
btcli subnets register --netuid NETUID --wallet-name test-miner --hotkey default --network ws://127.0.0.1:9944
btcli subnets register --netuid NETUID --wallet-name test-validator --hotkey default --network ws://127.0.0.1:9944
```

(Подстройте `--wallet-name` / `--hotkey` под созданные кошельки.)

Просмотр нейронов:

```powershell
btcli subnet show --netuid NETUID --network ws://127.0.0.1:9944
```

## Шаг 4 — Разрешение валидатора (validator permit, стейк)

Валидаторам нужен **validator permit** (см. [обзор валидаторов](https://docs.bittensor.com/validators)). На localnet обычно делают **стейк TAO** на hotkey валидатора:

```powershell
btcli stake add --netuid NETUID --wallet-name test-validator --hotkey default --partial --network ws://127.0.0.1:9944
```

Проверьте обзор: звёздочка `*` в колонке **VPERMIT** (или аналоге) значит, что валидатор допущен:

```powershell
btcli wallet overview --wallet.name test-validator --network ws://127.0.0.1:9944
```

Если permit сразу не появился, дождитесь конца **tempo** (раунда сабнета), как в [mine-validate](https://docs.bittensor.com/local-build/mine-validate).

## Шаг 5 — Шаблон сабнета (процессы майнера и валидатора)

Клонируйте официальный шаблон (или свой форк):

```powershell
git clone https://github.com/opentensor/subnet-template.git
cd subnet-template
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install bittensor
```

### Указать SDK на вашу ноду

В шаблоне часто используют `--subtensor.network local` с дефолтными локальными endpoint’ами. Если нужен явный URL, добавьте флаг из документации вашей версии `btcli`/SDK (часто **`--subtensor.chain_endpoint ws://127.0.0.1:9944`**) и для **`miner.py`**, и для **`validator.py`**.

### Запуск майнера (отдельный терминал)

Поднимает **Axon** (в примере порт **8901**; смените, если занят):

```powershell
python miner.py --wallet.name test-miner --wallet.hotkey default --netuid NETUID --axon.port 8901 --subtensor.network local --logging.info
```

### Запуск валидатора (другой терминал)

```powershell
python validator.py --wallet.name test-validator --wallet.hotkey default --netuid NETUID --subtensor.network local --logging.info
```

Должен пойти трафик заглушечного протокола (в шаблоне числа умножаются на два); после выставления весов в выводе `subnet show` меняются **incentive / dividends**:

```powershell
btcli subnet show --netuid NETUID --network ws://127.0.0.1:9944
```

## Путь к сабнету LLM text-to-text

Шаблон **намеренно простой** (класс `Dummy` в `protocol.py`). Для сценария **текст на входе → текст на выходе**:

1. **Опишите synapse** в `protocol.py` (например поля `prompt: str`, `response: str`, опционально `model_id`, ограничения длины). Наследуйтесь от типа synapse, который ожидает SDK (см. шаблон и [документацию Bittensor](https://docs.bittensor.com/)).  
2. **Майнер** (`miner.py`): в обработчике forward запускайте **генерацию текста** (локально HF `transformers`, vLLM, HTTP к API и т.д.), заполните `response`, верните результат. Учитывайте **латентность**, **GPU** и **таймауты**, которые задаст валидатор.  
3. **Валидатор** (`validator.py`): шлите промпты (фиксированный набор, сэмплы, датасет), собирайте ответы, **оценивайте** (метрики с эталоном, reward model, штраф за длину, проверки отказа). Сопоставьте скоры с **весами** по зарегистрированным UID (логика весов в шаблоне).  
4. **Эксплуатация**: откройте порт **Axon** в файрволе, для нескольких майнеров на одном хосте — **разные порты**, логируйте и ограничивайте частоту.  
5. **Продакшен**: на mainnet/testnet другие экономика, стоимость регистрации и гиперпараметры сабнета — перечитайте [Create a Subnet](https://docs.bittensor.com/subnets/create-a-subnet) для не-локального деплоя.

Отдельного «LLM-сабнета» в репозитории **subtensor** нет; продукт — ваш **Python-репозиторий**. Ищите в экосистеме открытые сабнеты, близкие по задаче (названия и API со временем меняются).

## Типичные проблемы

| Симптом | Что проверить |
| ------- | ------------- |
| `1006` / нет соединения | Цепочка не запущена или неверный `ws://` хост/порт; [`scripts/rpc-smoke`](scripts/rpc-smoke/README.md). |
| Недостаточно средств на create/register | Перевести TAO с Alice на coldkey подписанта ([provision wallets](https://docs.bittensor.com/local-build/provision-wallets)). |
| Майнер «not registered» | Выполнить `btcli subnets register` для нужного `NETUID` и endpoint. |
| `NeuronNoValidatorPermit` | Больше стейка на hotkey валидатора; дождаться tempo ([mine-validate](https://docs.bittensor.com/local-build/mine-validate)). |
| `WeightVecLengthIsLow` | Часто «майнеры недоступны» или слишком разреженный вектор весов; убедитесь, что Axon майнера поднят и валидатор достучится до IP/порта. |
| SubWallet / кошельки только с HTTPS | Локальный `ws://` — для **btcli / SDK / Polkadot JS**; для **wss** нужен TLS-прокси (см. обсуждение в [`RUN_LOCAL.md`](RUN_LOCAL.md)). |

## Ссылки

- [opentensor/subnet-template](https://github.com/opentensor/subnet-template)  
- [Создание сабнета (локально)](https://docs.bittensor.com/local-build/create-subnet)  
- [Майнинг и валидация на localnet](https://docs.bittensor.com/local-build/mine-validate)  
- [Запуск Subtensor локально](RUN_LOCAL.md) (этот форк)
