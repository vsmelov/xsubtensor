# subnet-navigation — доделать позже

- **Сабнет на цепи:** `subnet-navigation`, **netuid 4** (после `subnet create`). В `.env.subnet-navigation` выставлен `NETUID=4`.
- **Зарегистрированы:** владелец (uid 0), **nav-miner**, **nav-miner-b**, **nav-val** (uids 1–3). **nav-val-b** — не вошёл: лимит **3 burn-registration за интервал** (≈360 блоков) + ошибка `Custom error: 6` при 4-й подряд.
- **Дальше вручную:** когда пройдёт интервал, одна команда `btcli subnets register --netuid 4 --wallet-name nav-val-b ...` (как для math), затем при необходимости `stake add` для второго валидатора и `docker compose -f docker-compose.subnet-navigation.yml ... up -d` включая **nav-validator-b**.
- **Стейк** на netuid 4 для nav-val сейчас может отстреливать другой код (например `255`) — проверить баланс / лимиты / эпоху.
- **Лишние кошельки:** `nav-tmp` создавали для проверки — можно удалить с диска или игнорировать.
- Compose, порты **8933/8934**, **9133/9134**, probe **8096** — в `docker-compose.subnet-navigation.yml`; кратко в `SUBNET_NAVIGATION_LOCALNET.md`.
- **Эмиссия / pie chart:** без `subnet start` netuid 4 был 0% в доле minting; после **`subnet start`** (выполнено для nav-owner) навигация участвует в coinbase. Фиксированные **20/70/10** на цепи не задаются — см. **`MINTING_SHARE_SUBNETS.md`**.
