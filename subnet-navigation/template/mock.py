import hashlib
import json
import operator
import time

import asyncio
import random
from types import SimpleNamespace

import bittensor as bt
import numpy as np

from typing import List

from template.protocol import ALLOWED_OPS

_OPS = {"+": operator.add, "-": operator.sub, "*": operator.mul}
_DISCRETE_ACTION_IDS = (1, 2, 3, 4, 5, 8, 9, 10, 12)


def _stable_seed(*parts) -> int:
    raw = "|".join(str(part) for part in parts if part is not None)
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16], 16)


def _build_mock_navigation_proposal(synapse) -> dict:
    seed = _stable_seed(
        getattr(synapse, "request_id", None),
        getattr(synapse, "task_kind", None),
        getattr(synapse, "scene_id", None),
        getattr(synapse, "goal", None),
    )
    preferred_motion = ""
    constraints = getattr(synapse, "constraints", None) or {}
    if isinstance(constraints, dict):
        preferred_motion = str(constraints.get("preferred_motion_kind", "")).strip().lower()

    if preferred_motion == "world_delta":
        proposal = {
            "motion_kind": "world_delta",
            "action_id": 9,
            "world_dx_m": round((((seed % 2001) - 1000) / 1000.0) * 1.0, 4),
            "world_dy_m": round(((((seed // 7) % 2001) - 1000) / 1000.0) * 0.6, 4),
            "world_dz_m": 0.0,
            "world_dyaw_rad": round(((((seed // 13) % 2001) - 1000) / 1000.0) * 0.3, 4),
            "photo_name": "",
            "user_message": "",
        }
    else:
        action_id = _DISCRETE_ACTION_IDS[seed % len(_DISCRETE_ACTION_IDS)]
        proposal = {
            "motion_kind": "discrete",
            "action_id": int(action_id),
            "world_dx_m": 0.0,
            "world_dy_m": 0.0,
            "world_dz_m": 0.0,
            "world_dyaw_rad": 0.0,
            "photo_name": "mock-photo.jpg" if action_id == 10 else "",
            "user_message": "mock-user-message" if action_id == 12 else "",
        }

    proposal["explain"] = f"mock proposal for {getattr(synapse, 'request_id', 'navigation-task')}"
    proposal["request_id"] = getattr(synapse, "request_id", None)
    return proposal


class MockWallet:
    """
    Minimal stand-in for tests / --mock. Public SDK 9.7 does not ship bt.MockWallet on the
    top-level module; only hotkey/coldkey with ss58 are required for MockSubtensor.
    """

    def __init__(self, config=None):
        self.hotkey = bt.Keypair.create_from_uri("//subnet-navigation-mock-hotkey")
        self.coldkey = bt.Keypair.create_from_uri("//subnet-navigation-mock-coldkey")

    def __str__(self) -> str:
        return f"MockWallet({self.hotkey.ss58_address})"


class MockSubtensor(bt.MockSubtensor):
    def __init__(self, netuid, n=16, wallet=None, network="mock"):
        super().__init__(network=network)

        # SDK 9.7 MockSubtensor.subnet_exists() can return a truthy query wrapper
        # before the in-memory NetworksAdded map is initialized for this netuid.
        if netuid not in self.chain_state["SubtensorModule"]["NetworksAdded"]:
            self.create_subnet(netuid)

        registered = self.chain_state["SubtensorModule"]["Uids"].get(netuid, {})

        # Register ourself (the validator) as a neuron at uid=0
        if wallet is not None:
            if wallet.hotkey.ss58_address not in registered:
                self.force_register_neuron(
                    netuid=netuid,
                    hotkey=wallet.hotkey.ss58_address,
                    coldkey=wallet.coldkey.ss58_address,
                    balance=100000,
                    stake=100000,
                )

        # Register n mock neurons who will be miners
        for i in range(1, n + 1):
            hotkey = f"miner-hotkey-{i}"
            if hotkey not in registered:
                self.force_register_neuron(
                    netuid=netuid,
                    hotkey=hotkey,
                    coldkey="mock-coldkey",
                    balance=100000,
                    stake=100000,
                )


class MockMetagraph:
    def __init__(self, netuid=1, network="mock", subtensor=None):
        self.netuid = netuid
        self.network = network
        self.subtensor = subtensor
        raw_keys = (subtensor.chain_state["SubtensorModule"]["Keys"].get(netuid) or {}) if subtensor is not None else {}
        self.hotkeys = [
            str(value.get(0) if isinstance(value, dict) else value)
            for _, value in sorted(raw_keys.items())
        ]
        self.n = np.array(len(self.hotkeys), dtype=np.int64)
        self.last_update = np.zeros(len(self.hotkeys), dtype=np.int64)
        self.validator_permit = np.zeros(len(self.hotkeys), dtype=bool)
        self.S = np.zeros(len(self.hotkeys), dtype=np.float32)
        self.axons = [
            SimpleNamespace(
                ip="127.0.0.1",
                port=8091 + index,
                hotkey=hotkey,
                is_serving=True,
            )
            for index, hotkey in enumerate(self.hotkeys)
        ]

    def sync(self, *args, **kwargs):
        return self


class MockDendrite(bt.Dendrite):
    """
    Replaces a real bittensor network request with a mock request that just returns some static response for all axons that are passed and adds some random delay.
    """

    def __init__(self, wallet):
        super().__init__(wallet)
        self.keypair = wallet.hotkey

    async def forward(
        self,
        axons: List[bt.Axon],
        synapse: bt.Synapse = bt.Synapse(),
        timeout: float = 12,
        deserialize: bool = True,
        run_async: bool = True,
        streaming: bool = False,
    ):
        if streaming:
            raise NotImplementedError("Streaming not implemented yet.")

        async def query_all_axons(streaming: bool):
            """Queries all axons for responses."""

            async def single_axon_response(i, axon):
                """Queries a single axon for a response."""

                start_time = time.time()
                s = synapse.copy()
                # Attach some more required data so it looks real
                s = self.preprocess_synapse_for_request(axon, s, timeout)
                # We just want to mock the response, so we'll just fill in some data
                process_time = random.random()
                if process_time < timeout:
                    s.dendrite.process_time = str(time.time() - start_time)
                    # TODO (developer): replace with your own expected synapse data
                    has_navigation_payload = any(
                        getattr(s, attr, None) is not None
                        for attr in ("request_id", "goal", "scene_id", "context")
                    )
                    op = (s.op or "").strip()
                    if has_navigation_payload:
                        s.proposal = _build_mock_navigation_proposal(s)
                        s.result = None
                    elif op in ALLOWED_OPS:
                        ex = float(
                            _OPS[op](int(s.operand_a), int(s.operand_b))
                        )
                        s.result = ex + random.uniform(-0.1, 0.1)
                    else:
                        s.result = None
                    s.dendrite.status_code = 200
                    s.dendrite.status_message = "OK"
                    synapse.dendrite.process_time = str(process_time)
                else:
                    s.result = float(s.operand_a or 0.0)
                    s.dendrite.status_code = 408
                    s.dendrite.status_message = "Timeout"
                    synapse.dendrite.process_time = str(timeout)

                # Return the updated synapse object after deserializing if requested
                if deserialize:
                    return s.deserialize()
                else:
                    return s

            return await asyncio.gather(
                *(
                    single_axon_response(i, target_axon)
                    for i, target_axon in enumerate(axons)
                )
            )

        return await query_all_axons(streaming)

    def __str__(self) -> str:
        """
        Returns a string representation of the Dendrite object.

        Returns:
            str: The string representation of the Dendrite object in the format "dendrite(<user_wallet_address>)".
        """
        return "MockDendrite({})".format(self.keypair.ss58_address)
