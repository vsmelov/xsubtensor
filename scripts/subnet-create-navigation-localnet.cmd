@echo off
REM Создание сабнета subnet-navigation на localnet (владелец nav-owner). Лог: subnet-create-navigation.log
cd /d "%~dp0.."
docker compose -f docker-compose.subnet-navigation.yml --env-file .env.subnet-navigation run --rm -T -e HOME=/root --entrypoint btcli nav-miner subnet create --subnet-name subnet-navigation --wallet-name nav-owner --hotkey default --network ws://subtensor-localnet:9944 --github-repo https://github.com/opentensor/bittensor --subnet-contact dev@local.test --subnet-url https://example.com --discord-handle none --description localnet-navigation --additional-info none --no-prompt -p /root/.bittensor/wallets > subnet-create-navigation.log 2>&1
