@echo off
REM Полный список флагов и пересоздание сабнета: SUBNET_MATH_LOCALNET.md §4
REM Лог в корне репозитория: subnet-create.log
cd /d "%~dp0.."
docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math run --rm -T -e HOME=/root --entrypoint btcli math-miner subnet create --subnet-name subnet-math --wallet-name math-owner --hotkey default --network ws://subtensor-localnet:9944 --github-repo https://github.com/opentensor/bittensor --subnet-contact dev@local.test --subnet-url https://example.com --discord-handle none --description localnet-dev --additional-info none --no-prompt -p /root/.bittensor/wallets > subnet-create.log 2>&1
