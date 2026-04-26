#!/usr/bin/env python3
"""
Один запрос NavigationSynapse к майнеру по UID (нужен зарегистрированный coldkey/hotkey для подписи dendrite).

Запуск из корня репо, в той же Docker-сети, что и localnet (подставьте NETUID и кошелёк):

  docker compose -f docker-compose.subnet-navigation.yml --env-file .env.subnet-navigation run --rm -T \\
    --entrypoint python nav-miner scripts/query_miner.py \\
    --netuid 4 --wallet-name nav-val --miner-uid 1 \\
    --subtensor.chain_endpoint ws://subtensor-localnet:9944 \\
    --scene-id localnet-scene-1 \\
    --goal-instruction "Fly toward the highlighted checkpoint"
"""

from __future__ import annotations

import argparse
import asyncio

import bittensor as bt

from template.protocol import NavigationSynapse


async def _run(args: argparse.Namespace) -> None:
    wallet = bt.Wallet(name=args.wallet_name, hotkey=args.hotkey, path=args.wallet_path)
    subtensor = bt.Subtensor(network=args.chain)
    mg = subtensor.metagraph(args.netuid)
    if args.miner_uid < 0 or args.miner_uid >= mg.n:
        raise SystemExit(f"miner-uid out of range 0..{mg.n - 1}")
    axon = mg.axons[args.miner_uid]
    dendrite = bt.Dendrite(wallet)
    synapse = NavigationSynapse(
        request_id=args.request_id,
        task_kind="goal-conditioned-navigation",
        scene_id=args.scene_id,
        map_id=args.map_id,
        start={"kind": "origin", "coordinates": {"x": 0, "y": 0}},
        goal={"instruction": args.goal_instruction},
        constraints={"preferred_motion_kind": args.preferred_motion_kind},
        context={"probe": "query_miner.py"},
    )
    out = await dendrite(
        [axon], synapse=synapse, deserialize=False, timeout=args.timeout
    )
    print("axon:", axon)
    print("response:", out[0] if out else out)


def main() -> None:
    p = argparse.ArgumentParser(description="Single NavigationSynapse query to miner UID")
    p.add_argument("--netuid", type=int, required=True)
    p.add_argument("--wallet-name", required=True, help="Coldkey name (must be registered)")
    p.add_argument("--wallet-path", default="~/.bittensor", help="Directory containing wallet folders")
    p.add_argument("--hotkey", default="default")
    p.add_argument(
        "--subtensor.chain_endpoint",
        dest="chain",
        default="ws://127.0.0.1:9944",
        help="Inside Docker use ws://subtensor-localnet:9944",
    )
    p.add_argument("--miner-uid", type=int, required=True)
    p.add_argument("--request-id", default="manual-navigation-query")
    p.add_argument("--scene-id", default="localnet-scene")
    p.add_argument("--map-id", default="localnet-grid")
    p.add_argument("--goal-instruction", default="Move toward the safe checkpoint.")
    p.add_argument("--preferred-motion-kind", default="discrete")
    p.add_argument("--timeout", type=float, default=30.0)
    args = p.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
