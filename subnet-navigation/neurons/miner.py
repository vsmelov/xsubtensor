# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# TODO(developer): Set your name
# Copyright © 2023 <your name>

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import hashlib
import json
import operator
import random
import time
import typing

import bittensor as bt

# Bittensor Miner Template:
import template

# import base miner class which takes care of most of the boilerplate
from template.base.miner import BaseMinerNeuron
from template.protocol import ALLOWED_OPS
from template.runtime_client import runtime_base_url, runtime_timeout, try_post_json

_OPS = {"+": operator.add, "-": operator.sub, "*": operator.mul}
_DISCRETE_ACTION_IDS = (1, 2, 3, 4, 5, 8, 9, 10, 12)


def _goal_text(payload: typing.Any) -> str:
    if payload is None:
        return ""
    if isinstance(payload, dict):
        for key in ("instruction", "target", "goal", "label", "name"):
            value = payload.get(key)
            if value:
                return str(value)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return str(payload)


def _stable_seed(*parts: typing.Any) -> int:
    raw = "|".join(str(part) for part in parts if part is not None)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _bounded_delta(seed: int, *, max_abs: float) -> float:
    frac = ((seed % 2001) - 1000) / 1000.0
    return round(frac * max_abs, 4)


def _build_navigation_proposal(
    synapse: template.protocol.NavigationSynapse,
) -> dict[str, typing.Any]:
    seed = _stable_seed(
        synapse.request_id,
        synapse.task_kind,
        synapse.scene_id,
        synapse.map_id,
        _goal_text(synapse.goal),
        _goal_text(synapse.constraints),
    )
    constraints = synapse.constraints or {}
    preferred_motion = str(constraints.get("preferred_motion_kind", "")).strip().lower()
    use_world_delta = preferred_motion == "world_delta"
    if preferred_motion == "" and "continuous" in str(synapse.task_kind or "").lower():
        use_world_delta = True

    if use_world_delta:
        proposal = {
            "motion_kind": "world_delta",
            "action_id": 9,
            "world_dx_m": _bounded_delta(seed, max_abs=1.2),
            "world_dy_m": _bounded_delta(seed // 3 + 17, max_abs=0.7),
            "world_dz_m": 0.0,
            "world_dyaw_rad": _bounded_delta(seed // 7 + 31, max_abs=0.45),
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
            "photo_name": "miner-photo.jpg" if action_id == 10 else "",
            "user_message": (
                f"Navigation note for {synapse.request_id or synapse.scene_id or 'task'}"
                if action_id == 12
                else ""
            ),
        }

    proposal["explain"] = (
        f"{synapse.task_kind}: scene={synapse.scene_id or 'unknown'} "
        f"goal={_goal_text(synapse.goal)[:120] or 'unspecified'}"
    )
    proposal["request_id"] = synapse.request_id
    return proposal


def _normalize_navigation_proposal(
    payload: typing.Any,
    *,
    hotkey_ss58: str,
    fallback: dict[str, typing.Any],
) -> dict[str, typing.Any]:
    proposal = dict(payload) if isinstance(payload, dict) else dict(fallback)
    proposal.setdefault("miner_index", 0)
    proposal.setdefault("miner_hotkey", hotkey_ss58)
    proposal.setdefault("temperature", 0.0)
    proposal.setdefault("action_id", fallback.get("action_id", 1))
    proposal.setdefault("explain", fallback.get("explain", "navigation miner proposal"))
    proposal.setdefault(
        "raw_json",
        json.dumps(proposal, ensure_ascii=False, sort_keys=True),
    )
    proposal.setdefault("motion_kind", fallback.get("motion_kind", "discrete"))
    proposal.setdefault("world_dx_m", fallback.get("world_dx_m", 0.0))
    proposal.setdefault("world_dy_m", fallback.get("world_dy_m", 0.0))
    proposal.setdefault("world_dz_m", fallback.get("world_dz_m", 0.0))
    proposal.setdefault("world_dyaw_rad", fallback.get("world_dyaw_rad", 0.0))
    proposal.setdefault("photo_name", fallback.get("photo_name", ""))
    proposal.setdefault("user_message", fallback.get("user_message", ""))
    proposal.setdefault("elapsed_ms", 0.0)
    proposal.setdefault("request_id", fallback.get("request_id"))
    return proposal


class Miner(BaseMinerNeuron):
    """
    Your miner neuron class. You should use this class to define your miner's behavior. In particular, you should replace the forward function with your own logic. You may also want to override the blacklist and priority functions according to your needs.

    This class inherits from the BaseMinerNeuron class, which in turn inherits from BaseNeuron. The BaseNeuron class takes care of routine tasks such as setting up wallet, subtensor, metagraph, logging directory, parsing config, etc. You can override any of the methods in BaseNeuron if you need to customize the behavior.

    This class provides reasonable default behavior for a miner such as blacklisting unrecognized hotkeys, prioritizing requests based on stake, and forwarding requests to the forward function. If you need to define custom
    """

    def __init__(self, config=None):
        super(Miner, self).__init__(config=config)

        # TODO(developer): Anything specific to your use case you can do here

    async def forward(
        self, synapse: template.protocol.NavigationSynapse
    ) -> template.protocol.NavigationSynapse:
        has_navigation_payload = any(
            value is not None
            for value in (
                synapse.request_id,
                synapse.goal,
                synapse.scene_id,
                synapse.context,
            )
        )
        if has_navigation_payload:
            base_url = runtime_base_url(self.config)
            timeout_s = runtime_timeout(self.config)
            fallback_proposal = _build_navigation_proposal(synapse)
            runtime_payload = {
                "request_id": synapse.request_id or "navigation-request",
                "task_kind": synapse.task_kind,
                "scene_id": synapse.scene_id or "unknown-scene",
                "map_id": synapse.map_id,
                "start": synapse.start,
                "goal": synapse.goal,
                "constraints": synapse.constraints,
                "context": synapse.context,
                "validator_nonce": synapse.request_id or "runtime-nonce",
                "deadline_ms": int(timeout_s * 1000),
            }
            runtime_resp = try_post_json(base_url, "/internal/mine", runtime_payload, timeout_s)
            synapse.proposal = _normalize_navigation_proposal(
                runtime_resp,
                hotkey_ss58=str(self.wallet.hotkey.ss58_address),
                fallback=fallback_proposal,
            )
            synapse.result = None
            bt.logging.info(
                "Navigation proposal generated: "
                + json.dumps(synapse.proposal, ensure_ascii=False, sort_keys=True)
            )
            return synapse

        op = (synapse.op or "").strip()
        if op not in ALLOWED_OPS:
            synapse.result = None
            bt.logging.warning(f"Unsupported op {synapse.op!r}")
            return synapse
        fn = _OPS[op]
        exact = float(fn(int(synapse.operand_a), int(synapse.operand_b)))
        noise = random.uniform(-0.1, 0.1)
        synapse.result = exact + noise
        bt.logging.info(
            f"Math: {synapse.operand_a} {op} {synapse.operand_b} -> exact={exact} noisy={synapse.result}"
        )
        return synapse

    async def blacklist(
        self, synapse: template.protocol.NavigationSynapse
    ) -> typing.Tuple[bool, str]:
        """
        Determines whether an incoming request should be blacklisted and thus ignored. Your implementation should
        define the logic for blacklisting requests based on your needs and desired security parameters.

        Blacklist runs before the synapse data has been deserialized (i.e. before synapse.data is available).
        The synapse is instead contracted via the headers of the request. It is important to blacklist
        requests before they are deserialized to avoid wasting resources on requests that will be ignored.

        Args:
            synapse (template.protocol.NavigationSynapse): A synapse object constructed from the headers of the incoming request.

        Returns:
            Tuple[bool, str]: A tuple containing a boolean indicating whether the synapse's hotkey is blacklisted,
                            and a string providing the reason for the decision.

        This function is a security measure to prevent resource wastage on undesired requests. It should be enhanced
        to include checks against the metagraph for entity registration, validator status, and sufficient stake
        before deserialization of synapse data to minimize processing overhead.

        Example blacklist logic:
        - Reject if the hotkey is not a registered entity within the metagraph.
        - Consider blacklisting entities that are not validators or have insufficient stake.

        In practice it would be wise to blacklist requests from entities that are not validators, or do not have
        enough stake. This can be checked via metagraph.S and metagraph.validator_permit. You can always attain
        the uid of the sender via a metagraph.hotkeys.index( synapse.dendrite.hotkey ) call.

        Otherwise, allow the request to be processed further.
        """

        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            bt.logging.warning(
                "Received a request without a dendrite or hotkey."
            )
            return True, "Missing dendrite or hotkey"

        # TODO(developer): Define how miners should blacklist requests.
        uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
        if (
            not self.config.blacklist.allow_non_registered
            and synapse.dendrite.hotkey not in self.metagraph.hotkeys
        ):
            # Ignore requests from un-registered entities.
            bt.logging.trace(
                f"Blacklisting un-registered hotkey {synapse.dendrite.hotkey}"
            )
            return True, "Unrecognized hotkey"

        if self.config.blacklist.force_validator_permit:
            # If the config is set to force validator permit, then we should only allow requests from validators.
            if not self.metagraph.validator_permit[uid]:
                bt.logging.warning(
                    f"Blacklisting a request from non-validator hotkey {synapse.dendrite.hotkey}"
                )
                return True, "Non-validator hotkey"

        bt.logging.trace(
            f"Not Blacklisting recognized hotkey {synapse.dendrite.hotkey}"
        )
        return False, "Hotkey recognized!"

    async def priority(self, synapse: template.protocol.NavigationSynapse) -> float:
        """
        The priority function determines the order in which requests are handled. More valuable or higher-priority
        requests are processed before others. You should design your own priority mechanism with care.

        This implementation assigns priority to incoming requests based on the calling entity's stake in the metagraph.

        Args:
            synapse (template.protocol.NavigationSynapse): The synapse object that contains metadata about the incoming request.

        Returns:
            float: A priority score derived from the stake of the calling entity.

        Miners may receive messages from multiple entities at once. This function determines which request should be
        processed first. Higher values indicate that the request should be processed first. Lower values indicate
        that the request should be processed later.

        Example priority logic:
        - A higher stake results in a higher priority value.
        """
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            bt.logging.warning(
                "Received a request without a dendrite or hotkey."
            )
            return 0.0

        # TODO(developer): Define how miners should prioritize requests.
        caller_uid = self.metagraph.hotkeys.index(
            synapse.dendrite.hotkey
        )  # Get the caller index.
        priority = float(
            self.metagraph.S[caller_uid]
        )  # Return the stake as the priority.
        bt.logging.trace(
            f"Prioritizing {synapse.dendrite.hotkey} with value: {priority}"
        )
        return priority


# This is the main function, which runs the miner.
if __name__ == "__main__":
    with Miner() as miner:
        while True:
            bt.logging.info(f"Miner running... {time.time()}")
            time.sleep(5)
