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

import json
import math
import time

import bittensor as bt
import numpy as np

from template.protocol import NavigationSynapse
from template.runtime_client import runtime_base_url, runtime_timeout, try_post_json
from template.validator.reward import get_rewards
from template.utils.uids import get_random_uids

_COMPAT_ACTION_IDS = (1, 2, 3, 4, 5, 8, 9, 10, 12)


def _lookup(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _coerce_float(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compat_navigation_proposal(response, miner_uid, miner_hotkey, request_id):
    scalar = _coerce_float(_lookup(response, "result"))
    seed = int(abs((scalar or 0.0) * 1000.0)) + int(miner_uid) * 17
    action_id = _COMPAT_ACTION_IDS[seed % len(_COMPAT_ACTION_IDS)]
    motion_kind = "world_delta" if action_id == 9 else "discrete"
    proposal = {
        "miner_index": int(miner_uid),
        "miner_hotkey": miner_hotkey,
        "temperature": 0.0,
        "action_id": int(action_id),
        "explain": f"compat proposal synthesized from legacy scalar result={scalar!r}",
        "motion_kind": motion_kind,
        "world_dx_m": 0.0,
        "world_dy_m": 0.0,
        "world_dz_m": 0.0,
        "world_dyaw_rad": 0.0,
        "photo_name": "",
        "user_message": "",
        "elapsed_ms": 0.0,
        "request_id": request_id,
    }
    if motion_kind == "world_delta" and scalar is not None:
        proposal["world_dx_m"] = round(max(-1.2, min(1.2, scalar / 50.0)), 4)
        proposal["world_dy_m"] = round(max(-0.7, min(0.7, scalar / 80.0)), 4)
        proposal["world_dyaw_rad"] = round(max(-0.45, min(0.45, scalar / 120.0)), 4)
    proposal["raw_json"] = json.dumps(proposal, ensure_ascii=False, sort_keys=True)
    return proposal


def _build_navigation_synapse(step: int) -> NavigationSynapse:
    direction = "north-east" if step % 2 == 0 else "toward the highlighted checkpoint"
    return NavigationSynapse(
        request_id=f"nav-step-{step}",
        task_kind="goal-conditioned-navigation",
        scene_id=f"localnet-scene-{step % 3}",
        map_id="localnet-grid",
        start={"pose_id": step, "x": float(step), "y": float(step) / 2.0},
        goal={
            "instruction": f"Move {direction} and keep safe clearance from obstacles.",
            "checkpoint_index": step % 5,
        },
        constraints={
            "preferred_motion_kind": "world_delta" if step % 3 == 0 else "discrete",
            "max_step_m": 1.2,
            "max_yaw_rad": 0.45,
        },
        context={
            "recent_actions": [max(0, step - 1), step],
            "mission_reference": f"mission-{step % 4}",
        },
    )


def _score_navigation_response(proposal, process_time_s=None) -> tuple[float, dict[str, float], str]:
    if not proposal:
        return 0.0, {
            "overall": 0.0,
            "safety": 0.0,
            "task_match": 0.0,
            "speed": 0.0,
        }, "missing proposal"

    motion_kind = str(_lookup(proposal, "motion_kind", "discrete"))
    explain = str(_lookup(proposal, "explain", "") or "")
    action_id = int(_lookup(proposal, "action_id", 0) or 0)
    dx = _coerce_float(_lookup(proposal, "world_dx_m", 0.0)) or 0.0
    dy = _coerce_float(_lookup(proposal, "world_dy_m", 0.0)) or 0.0
    dz = _coerce_float(_lookup(proposal, "world_dz_m", 0.0)) or 0.0
    dyaw = _coerce_float(_lookup(proposal, "world_dyaw_rad", 0.0)) or 0.0
    norm = math.sqrt(dx * dx + dy * dy + dz * dz)

    safety = 0.92 if motion_kind == "discrete" else max(0.45, 0.95 - min(0.45, norm * 0.22))
    task_match = 0.55 + (0.15 if explain else 0.0) + (0.1 if action_id not in (0,) else 0.0)
    if process_time_s is None:
        speed = 0.75
    else:
        speed = max(0.3, 1.0 - min(0.7, process_time_s / 6.0))
    yaw_penalty = min(0.15, abs(dyaw) * 0.05)
    overall = max(0.0, min(1.0, 0.4 * safety + 0.4 * task_match + 0.2 * speed - yaw_penalty))
    components = {
        "overall": round(overall, 4),
        "safety": round(max(0.0, min(1.0, safety)), 4),
        "task_match": round(max(0.0, min(1.0, task_match)), 4),
        "speed": round(max(0.0, min(1.0, speed)), 4),
    }
    reason = f"motion={motion_kind} action={action_id} norm={norm:.3f} dyaw={dyaw:.3f}"
    return overall, components, reason


def _response_to_payload(response, miner_uid: int, miner_hotkey: str, request_id: str) -> dict:
    proposal = _lookup(response, "proposal")
    dendrite = _lookup(response, "dendrite")
    if not isinstance(proposal, dict):
        proposal = _compat_navigation_proposal(
            response,
            miner_uid=miner_uid,
            miner_hotkey=miner_hotkey,
            request_id=request_id,
        )
    process_time = _coerce_float(_lookup(dendrite, "process_time"))
    return {
        "miner_index": int(_lookup(proposal, "miner_index", miner_uid)),
        "miner_hotkey": str(_lookup(proposal, "miner_hotkey", miner_hotkey)),
        "temperature": float(_coerce_float(_lookup(proposal, "temperature", 0.0)) or 0.0),
        "action_id": int(_lookup(proposal, "action_id", 0) or 0),
        "explain": str(_lookup(proposal, "explain", "") or ""),
        "raw_json": str(
            _lookup(
                proposal,
                "raw_json",
                json.dumps(proposal, ensure_ascii=False, sort_keys=True),
            )
        ),
        "motion_kind": str(_lookup(proposal, "motion_kind", "discrete") or "discrete"),
        "world_dx_m": float(_coerce_float(_lookup(proposal, "world_dx_m", 0.0)) or 0.0),
        "world_dy_m": float(_coerce_float(_lookup(proposal, "world_dy_m", 0.0)) or 0.0),
        "world_dz_m": float(_coerce_float(_lookup(proposal, "world_dz_m", 0.0)) or 0.0),
        "world_dyaw_rad": float(_coerce_float(_lookup(proposal, "world_dyaw_rad", 0.0)) or 0.0),
        "photo_name": _lookup(proposal, "photo_name", ""),
        "user_message": _lookup(proposal, "user_message", ""),
        "elapsed_ms": float(
            _coerce_float(_lookup(proposal, "elapsed_ms")) or (
                0.0 if process_time is None else process_time * 1000.0
            )
        ),
    }


def _reward_array(values) -> np.ndarray:
    if not values:
        return np.zeros(0, dtype=np.float32)
    return np.asarray([float(_coerce_float(value) or 0.0) for value in values], dtype=np.float32)


def _runtime_score_components(judge_row):
    if not judge_row:
        return {"overall": 0.0, "safety": 0.0, "task_match": 0.0, "speed": 0.0}
    return {
        "overall": float(_coerce_float(_lookup(judge_row, "overall")) or 0.0) / 100.0,
        "safety": float(_coerce_float(_lookup(judge_row, "safety")) or 0.0) / 100.0,
        "task_match": float(_coerce_float(_lookup(judge_row, "task_match")) or 0.0) / 100.0,
        "speed": float(_coerce_float(_lookup(judge_row, "speed")) or 0.0) / 100.0,
    }


async def forward(self):
    """
    The forward function is called by the validator every time step.

    It is responsible for querying the network and scoring the responses.

    Args:
        self (:obj:`bittensor.neuron.Neuron`): The neuron object which contains all the necessary state for the validator.

    """
    # TODO(developer): Define how the validator selects a miner to query, how often, etc.
    # get_random_uids is an example method, but you can replace it with your own.
    miner_uids = get_random_uids(self, k=self.config.neuron.sample_size)
    synapse = _build_navigation_synapse(int(self.step))
    responses = await self.dendrite(
        axons=[self.metagraph.axons[uid] for uid in miner_uids],
        synapse=synapse,
        deserialize=False,
    )
    proposal_payloads = [
        _response_to_payload(
            response,
            miner_uid=int(uid),
            miner_hotkey=str(self.metagraph.hotkeys[int(uid)]),
            request_id=synapse.request_id or f"nav-step-{self.step}",
        )
        for uid, response in zip(miner_uids, responses)
    ]
    runtime_timeout_s = runtime_timeout(self.config)
    runtime_payload = {
        "subnet": "drone-navigation",
        "job_id": synapse.request_id,
        "episode_id": synapse.request_id,
        "step_index": int(self.step),
        "validator_hotkey": str(self.wallet.hotkey.ss58_address),
        "validator_nonce": synapse.request_id,
        "state_hash": synapse.request_id,
        "deadline_ms": int(runtime_timeout_s * 1000),
        "synapse": {
            "request_id": synapse.request_id,
            "task_kind": synapse.task_kind,
            "scene_id": synapse.scene_id,
            "map_id": synapse.map_id,
            "start": synapse.start,
            "goal": synapse.goal,
            "constraints": synapse.constraints,
            "context": synapse.context,
            "validator_nonce": synapse.request_id,
            "deadline_ms": int(runtime_timeout_s * 1000),
        },
        "proposals": proposal_payloads,
    }
    runtime_resp = try_post_json(
        runtime_base_url(self.config),
        "/internal/verify-round",
        runtime_payload,
        runtime_timeout_s,
    )

    score_rows = []
    rewards = np.zeros(len(responses), dtype=np.float32)
    if isinstance(runtime_resp, dict) and runtime_resp.get("proposals"):
        judge_rows = list((_lookup(runtime_resp, "judge") or {}).get("candidate_scores") or [])
        reward_values = runtime_resp.get("normalized_weight_signals") or runtime_resp.get("rewards") or []
        rewards = _reward_array(reward_values)
        if rewards.size != len(responses):
            rewards = get_rewards(self, expected=None, responses=responses)
        for idx, (uid, response, runtime_row) in enumerate(zip(miner_uids, responses, runtime_resp.get("proposals") or [])):
            judge_row = next(
                (
                    row
                    for row in judge_rows
                    if int(_lookup(row, "miner_index", -1)) == int(_lookup(runtime_row, "miner_index", -1))
                ),
                None,
            )
            response.score = float(rewards[idx]) if idx < rewards.size else 0.0
            response.score_components = _runtime_score_components(judge_row)
            response.score_reason = str(_lookup(judge_row, "explain", "") or "runtime verifier")
            response.proposal = runtime_row
            score_rows.append(
                {
                    "uid": int(uid),
                    "hotkey": str(self.metagraph.hotkeys[int(uid)]),
                    "score": round(float(response.score), 4),
                    "components": response.score_components,
                    "reason": response.score_reason,
                    "proposal": runtime_row,
                }
            )
        if rewards.size == 0:
            rewards = get_rewards(self, expected=None, responses=responses)
        scoreboard = {
            "mode": "navigation-runtime",
            "request_id": synapse.request_id,
            "scene_id": synapse.scene_id,
            "task_kind": synapse.task_kind,
            "goal": synapse.goal,
            "uids": [int(u) for u in miner_uids],
            "responses": score_rows,
            "rewards": [float(x) for x in rewards.tolist()],
            "runtime_judge": _lookup(runtime_resp, "judge"),
            "winner_miner_index": _lookup(runtime_resp, "winner_miner_index"),
        }
    else:
        for uid, response, proposal_payload in zip(miner_uids, responses, proposal_payloads):
            process_time_s = _coerce_float(_lookup(_lookup(response, "dendrite"), "process_time"))
            score, components, reason = _score_navigation_response(
                proposal_payload,
                process_time_s=process_time_s,
            )
            response.score = score
            response.score_components = components
            response.score_reason = reason
            response.proposal = proposal_payload
            score_rows.append(
                {
                    "uid": int(uid),
                    "hotkey": str(self.metagraph.hotkeys[int(uid)]),
                    "score": round(score, 4),
                    "components": components,
                    "reason": reason,
                    "proposal": proposal_payload,
                }
            )

        rewards = get_rewards(self, expected=None, responses=responses)
        scoreboard = {
            "mode": "navigation-fallback",
            "request_id": synapse.request_id,
            "scene_id": synapse.scene_id,
            "task_kind": synapse.task_kind,
            "goal": synapse.goal,
            "uids": [int(u) for u in miner_uids],
            "responses": score_rows,
            "rewards": [float(x) for x in rewards.tolist()],
        }
    bt.logging.info("NAVIGATION_SCOREBOARD " + json.dumps(scoreboard, ensure_ascii=False))

    bt.logging.info(f"Scored responses: {rewards}")
    # Update the scores based on the rewards. You may want to define your own update_scores function for custom behavior.
    self.update_scores(rewards, miner_uids)
    time.sleep(float(self.config.neuron.forward_sleep))
