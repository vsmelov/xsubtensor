# Доля minting / emission по сабнетам (localnet)

## Почему subnet-navigation был 0%

Пока владелец не вызывает **`btcli subnet start`** для netuid, в сторедже нет `FirstEmissionBlockNumber`, и **coinbase не включает этот сабнет** в раздачу блоковой эмиссии (см. `run_coinbase.rs`: фильтр по `FirstEmissionBlockNumber`).

После успешного **`subnet start`** навигация попадает в общий пул и начинает получать ненулевую долю (как только UI пересчитает снимок).

Команда (владелец `nav-owner`, netuid **4**):

```text
docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math run --rm -T -e HOME=/root --entrypoint btcli math-miner subnet start --netuid 4 --wallet-name nav-owner --hotkey default --network ws://subtensor-localnet:9944 --no-prompt -p /root/.bittensor/wallets
```

(Можно вынести в отдельный compose только для btcli — суть та же.)

## Можно ли задать ровно 20% / 70% / 10% (navigation / vla / math)?

**Нет, как фиксированный переключатель на цепи.** В рантайме Subtensor доля **TAO в coinbase между сабнетами** (у которых уже стартовала эмиссия) считается **пропорционально сумме `moving_alpha_price` (EMA цены альфы)** по каждому сабнету, а не по введённым процентам. Это не root-веса по netuid в смысле «20/70/10».

Поэтому:

- **Точные** 20 / 70 / 10 **не гарантируются** без правки логики паллеты / кастомного рантайма.
- **Приблизить** картину можно только косвенно (объёмы пулов, стейк, торговля → цены → EMA), это долго и нестабильно на dev-сети.

## Что разумно сделать для «красоты» в UI

1. Убедиться, что у **всех трёх** сабнетов вызван **`subnet start`** (у math/vla обычно уже было).
2. В **`GET /v1/network-snapshot`** смотреть блок **`minting_share_hint`**: по умолчанию **`minting_share_mode=dashboard_fallback`** — новый сабнет не обязан быть 0% в диаграмме, пока EMA цены нулевая. Для строгого соответствия «как coinbase» в момент нулевой EMA: **`?minting_share_mode=chain_ema`**.
3. Для **жёстко заданных** 20/70/10 — множители **только во фронте** (off-chain), с подписью illustrative.

## Менять «цену альфы» вручную

Без **swap/stake** на сабнете или правок рантайма **нечем**: цена и EMA живут в сторедже и обновляются логикой паллеты. Для неравных долей на dev-сети проще **подстроить UI** (`minting_share_hint` или свои веса), чем «прикрутить» фиксированные проценты on-chain.
