@echo off
REM Запуск эмиссии для subnet-navigation (netuid 4), владелец nav-owner. Лог: subnet-start-navigation.log
cd /d "%~dp0.."
docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math run --rm -T -e HOME=/root --entrypoint btcli math-miner subnet start --netuid 4 --wallet-name nav-owner --hotkey default --network ws://subtensor-localnet:9944 --no-prompt -p /root/.bittensor/wallets > subnet-start-navigation.log 2>&1
