@echo off
REM Требуется переменная окружения SUBNET_LOCALNET_NETUID (число из subnet-create.log или subnets list).
REM PowerShell: $env:SUBNET_LOCALNET_NETUID = "2"; Start-Process cmd.exe -ArgumentList "/c", "`"$PWD\scripts\subnet-start-localnet.cmd`"" -WindowStyle Minimized
cd /d "%~dp0.."
if not defined SUBNET_LOCALNET_NETUID (
  echo ERROR: set SUBNET_LOCALNET_NETUID to your netuid, e.g. set SUBNET_LOCALNET_NETUID=2
  exit /b 1
)
docker compose -f docker-compose.subnet-math.yml --env-file .env.subnet-math run --rm -T -e HOME=/root --entrypoint btcli math-miner subnet start --netuid %SUBNET_LOCALNET_NETUID% --wallet-name math-owner --hotkey default --network ws://subtensor-localnet:9944 --no-prompt -p /root/.bittensor/wallets > subnet-start.log 2>&1
