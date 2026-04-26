"""
One dendrite pass over several miner UIDs with a navigation-shaped envelope.

Primary mode:
- send a `NavigationSynapse` to on-chain miners;
- collect their proposals;
- submit the round to navigation-runtime for scoring.

Fallback mode:
- if navigation-runtime is not configured or unavailable, score proposals locally with the
  same navigation-style envelope shape so the probe remains usable for local smoke tests.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import bittensor as bt
import numpy as np

from template.protocol import ALLOWED_OPS, NavigationSynapse
from template.runtime_client import try_post_json
from template.validator.reward import get_rewards

_COMPAT_ACTION_IDS = (1, 2, 3, 4, 5, 8, 9, 10, 12)


class _RewardLogCtx:
    """Minimal self for get_rewards."""


def _pick_miner_uids(
    mg: bt.metagraph,
    miner_uids: Optional[List[int]],
    sample_size: int,
) -> List[int]:
    n = int(mg.n)
    if miner_uids:
        uids = [int(u) for u in miner_uids if 0 <= int(u) < n]
        if not uids:
            raise ValueError("miner_uids empty or out of metagraph range")
        return uids

    k = max(1, min(int(sample_size), n))
    candidates = [
        u
        for u in range(n)
        if mg.axons[u].is_serving and not bool(mg.validator_permit[u])
    ]
    if len(candidates) < k:
        candidates = [u for u in range(n) if mg.axons[u].is_serving]
    if len(candidates) < k:
        candidates = list(range(n))
    return candidates[: min(k, len(candidates))]


def _coerce_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _lookup(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _dendrite_meta(synapse: Any) -> Any:
    d = getattr(synapse, "dendrite", None)
    if d is None:
        return None
    meta: dict[str, Any] = {}
    for attr in ("status_code", "status_message", "process_time", "ip", "port"):
        if hasattr(d, attr):
            value = getattr(d, attr)
            try:
                meta[attr] = value
            except Exception:
                meta[attr] = str(value)
    return meta if meta else str(d)


def _axon_meta(mg: bt.metagraph, uid: int) -> dict[str, Any]:
    ax = mg.axons[uid]
    hotkey = getattr(ax, "hotkey", None)
    return {
        "ip": getattr(ax, "ip", None),
        "port": getattr(ax, "port", None),
        "is_serving": getattr(ax, "is_serving", None),
        "hotkey": str(hotkey) if hotkey is not None else None,
    }


def _hotkey_at(mg: bt.metagraph, uid: int) -> Optional[str]:
    try:
        return str(mg.hotkeys[uid])
    except Exception:
        return None


def _synapse_payload(item: Any) -> Any:
    if item is None:
        return None
    out: dict[str, Any] = {
        "result": getattr(item, "result", None),
        "proposal": getattr(item, "proposal", None),
        "score": getattr(item, "score", None),
        "score_components": getattr(item, "score_components", None),
        "score_reason": getattr(item, "score_reason", None),
        "dendrite": _dendrite_meta(item),
    }
    for key in (
        "request_id",
        "task_kind",
        "scene_id",
        "map_id",
        "start",
        "goal",
        "constraints",
        "context",
    ):
        if hasattr(item, key):
            out[key] = getattr(item, key)
    return out


def _compat_navigation_proposal(
    *,
    response: Any,
    miner_uid: int,
    miner_hotkey: str,
    request_id: str,
) -> dict[str, Any]:
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


def _response_to_payload(
    *,
    response: Any,
    miner_uid: int,
    miner_hotkey: str,
    request_id: str,
) -> dict[str, Any]:
    proposal = _lookup(response, "proposal")
    if not isinstance(proposal, dict):
        proposal = _compat_navigation_proposal(
            response=response,
            miner_uid=miner_uid,
            miner_hotkey=miner_hotkey,
            request_id=request_id,
        )
    process_time = _coerce_float(_lookup(_lookup(response, "dendrite"), "process_time"))
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
        "photo_name": str(_lookup(proposal, "photo_name", "") or ""),
        "user_message": str(_lookup(proposal, "user_message", "") or ""),
        "elapsed_ms": float(
            _coerce_float(_lookup(proposal, "elapsed_ms")) or (
                0.0 if process_time is None else process_time * 1000.0
            )
        ),
    }


def _score_navigation_response(proposal: dict[str, Any], process_time_s: Optional[float]) -> tuple[float, dict[str, float], str]:
    motion_kind = str(_lookup(proposal, "motion_kind", "discrete"))
    explain = str(_lookup(proposal, "explain", "") or "")
    action_id = int(_lookup(proposal, "action_id", 0) or 0)
    dx = _coerce_float(_lookup(proposal, "world_dx_m", 0.0)) or 0.0
    dy = _coerce_float(_lookup(proposal, "world_dy_m", 0.0)) or 0.0
    dz = _coerce_float(_lookup(proposal, "world_dz_m", 0.0)) or 0.0
    dyaw = _coerce_float(_lookup(proposal, "world_dyaw_rad", 0.0)) or 0.0
    norm = float(np.sqrt(dx * dx + dy * dy + dz * dz))

    safety = 0.92 if motion_kind == "discrete" else max(0.45, 0.95 - min(0.45, norm * 0.22))
    task_match = 0.55 + (0.15 if explain else 0.0) + (0.1 if action_id != 0 else 0.0)
    speed = 0.75 if process_time_s is None else max(0.3, 1.0 - min(0.7, process_time_s / 6.0))
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


def _runtime_score_components(judge_row: Any) -> dict[str, float]:
    if not judge_row:
        return {"overall": 0.0, "safety": 0.0, "task_match": 0.0, "speed": 0.0}
    return {
        "overall": float(_coerce_float(_lookup(judge_row, "overall")) or 0.0) / 100.0,
        "safety": float(_coerce_float(_lookup(judge_row, "safety")) or 0.0) / 100.0,
        "task_match": float(_coerce_float(_lookup(judge_row, "task_match")) or 0.0) / 100.0,
        "speed": float(_coerce_float(_lookup(judge_row, "speed")) or 0.0) / 100.0,
    }


def _goal_payload(goal: Optional[Dict[str, Any]], mission_prompt: Optional[str]) -> Dict[str, Any]:
    if goal:
        return goal
    if mission_prompt:
        return {"instruction": mission_prompt}
    return {
        "kind": "coordinate_2d",
        "coordinates": {"x": 6, "y": 7},
        "instruction": "Move toward the safe checkpoint.",
    }


async def run_navigation_probe(
    *,
    netuid: int,
    chain_endpoint: str,
    wallet_name: str,
    hotkey: str = "default",
    miner_uids: Optional[List[int]] = None,
    sample_size: int = 4,
    timeout: float = 30.0,
    scene_id: Optional[str] = None,
    map_id: Optional[str] = None,
    goal: Optional[Dict[str, Any]] = None,
    start: Optional[Dict[str, Any]] = None,
    constraints: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    mission_prompt: Optional[str] = None,
    runtime_base_url: Optional[str] = None,
    runtime_timeout: Optional[float] = None,
    operand_a: Optional[int] = None,
    operand_b: Optional[int] = None,
    op: Optional[str] = None,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    if op and op not in ALLOWED_OPS:
        return {"ok": False, "error": f"op must be one of {ALLOWED_OPS}"}

    wallet = bt.Wallet(name=wallet_name, hotkey=hotkey)
    subtensor = bt.Subtensor(network=chain_endpoint)
    mg = subtensor.metagraph(netuid)

    uids_list = _pick_miner_uids(mg, miner_uids, sample_size)
    request_id = request_id or f"nav-probe-{int(time.time() * 1000)}"
    compat_legacy_input = None
    if operand_a is not None or operand_b is not None or op:
        compat_legacy_input = {
            "operand_a": operand_a,
            "operand_b": operand_b,
            "op": op,
        }

    synapse = NavigationSynapse(
        request_id=request_id,
        task_kind="goal-conditioned-navigation",
        scene_id=scene_id or "localnet-dev-scene",
        map_id=map_id or "localnet-grid",
        start=start or {"kind": "origin", "coordinates": {"x": 0, "y": 0}},
        goal=_goal_payload(goal, mission_prompt),
        constraints={"max_steps": 1, "timeout_s": timeout, **(constraints or {})},
        context={
            **({"legacy_input": compat_legacy_input} if compat_legacy_input else {}),
            **(context or {}),
        },
    )
    axons = [mg.axons[u] for u in uids_list]

    dendrite = bt.Dendrite(wallet)
    t_call = time.perf_counter()
    raw_out = None
    try:
        raw_out = await dendrite(
            axons,
            synapse=synapse,
            deserialize=False,
            timeout=timeout,
        )
    except TypeError:
        raw_out = await dendrite(
            axons,
            synapse=synapse,
            deserialize=True,
            timeout=timeout,
        )
    t_after = time.perf_counter()

    raw_list = list(raw_out) if isinstance(raw_out, (list, tuple)) else ([raw_out] if raw_out is not None else [])
    proposal_payloads = [
        _response_to_payload(
            response=raw_list[idx] if idx < len(raw_list) else None,
            miner_uid=int(uid),
            miner_hotkey=_hotkey_at(mg, int(uid)) or f"uid-{uid}",
            request_id=request_id,
        )
        for idx, uid in enumerate(uids_list)
    ]

    resolved_runtime_timeout = float(runtime_timeout or timeout)
    runtime_payload = {
        "subnet": "drone-navigation",
        "job_id": request_id,
        "episode_id": request_id,
        "step_index": 0,
        "validator_hotkey": str(wallet.hotkey.ss58_address),
        "validator_nonce": request_id,
        "state_hash": request_id,
        "deadline_ms": int(resolved_runtime_timeout * 1000),
        "synapse": {
            "request_id": synapse.request_id,
            "task_kind": synapse.task_kind,
            "scene_id": synapse.scene_id,
            "map_id": synapse.map_id,
            "start": synapse.start,
            "goal": synapse.goal,
            "constraints": synapse.constraints,
            "context": synapse.context,
            "validator_nonce": request_id,
            "deadline_ms": int(resolved_runtime_timeout * 1000),
        },
        "proposals": proposal_payloads,
    }
    runtime_resp = try_post_json(
        (runtime_base_url or "").rstrip("/"),
        "/internal/verify-round",
        runtime_payload,
        resolved_runtime_timeout,
    )

    miners: List[dict[str, Any]] = []
    rewards = np.zeros(len(uids_list), dtype=np.float32)
    runtime_mode = "navigation-fallback"
    if isinstance(runtime_resp, dict) and runtime_resp.get("proposals"):
        runtime_mode = "navigation-runtime"
        judge_rows = list((_lookup(runtime_resp, "judge") or {}).get("candidate_scores") or [])
        reward_values = runtime_resp.get("normalized_weight_signals") or runtime_resp.get("rewards") or []
        rewards = np.asarray([float(_coerce_float(v) or 0.0) for v in reward_values], dtype=np.float32)
        if rewards.size != len(uids_list):
            rewards = np.zeros(len(uids_list), dtype=np.float32)
        for idx, uid in enumerate(uids_list):
            item = raw_list[idx] if idx < len(raw_list) else None
            proposal = (runtime_resp.get("proposals") or [])[idx]
            judge_row = next(
                (
                    row
                    for row in judge_rows
                    if int(_lookup(row, "miner_index", -1)) == int(_lookup(proposal, "miner_index", -1))
                ),
                None,
            )
            score = float(rewards[idx]) if idx < rewards.size else 0.0
            score_components = _runtime_score_components(judge_row)
            score_reason = str(_lookup(judge_row, "explain", "") or "runtime verifier")
            if item is not None:
                item.proposal = proposal
                item.score = score
                item.score_components = score_components
                item.score_reason = score_reason
            miners.append(
                {
                    "uid": int(uid),
                    "hotkey_ss58": _hotkey_at(mg, int(uid)),
                    "axon": _axon_meta(mg, int(uid)),
                    "synapse": _synapse_payload(item),
                    "proposal": proposal,
                    "scoring_envelope": {
                        "mode": "navigation-runtime",
                        "score": score,
                        "components": score_components,
                        "reason": score_reason,
                    },
                    "reward_share": score,
                }
            )
        if rewards.size == 0:
            rewards = get_rewards(_RewardLogCtx(), expected=None, responses=raw_list)
    else:
        for idx, uid in enumerate(uids_list):
            item = raw_list[idx] if idx < len(raw_list) else None
            proposal = proposal_payloads[idx]
            process_time_s = _coerce_float(_lookup(_lookup(item, "dendrite"), "process_time"))
            score, score_components, score_reason = _score_navigation_response(
                proposal,
                process_time_s,
            )
            if item is not None:
                item.proposal = proposal
                item.score = score
                item.score_components = score_components
                item.score_reason = score_reason
            miners.append(
                {
                    "uid": int(uid),
                    "hotkey_ss58": _hotkey_at(mg, int(uid)),
                    "axon": _axon_meta(mg, int(uid)),
                    "synapse": _synapse_payload(item),
                    "proposal": proposal,
                    "scoring_envelope": {
                        "mode": "navigation-fallback",
                        "score": score,
                        "components": score_components,
                        "reason": score_reason,
                    },
                }
            )
        rewards = get_rewards(_RewardLogCtx(), expected=None, responses=raw_list)
        for idx, reward in enumerate(rewards.tolist()):
            miners[idx]["reward_share"] = float(reward)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    call_ms = int((t_after - t_call) * 1000)

    return {
        "ok": True,
        "protocol": "subnet-navigation NavigationSynapse",
        "runtime_mode": runtime_mode,
        "runtime_base_url": (runtime_base_url or "").rstrip("/"),
        "netuid": netuid,
        "chain_endpoint": chain_endpoint,
        "wallet_coldkey": wallet_name,
        "request": {
            "request_id": synapse.request_id,
            "task_kind": synapse.task_kind,
            "scene_id": synapse.scene_id,
            "map_id": synapse.map_id,
            "start": synapse.start,
            "goal": synapse.goal,
            "constraints": synapse.constraints,
            "context": synapse.context,
            **({"compat_legacy_input": compat_legacy_input} if compat_legacy_input else {}),
        },
        "miner_uids_queried": uids_list,
        "miners": miners,
        "rewards": [float(x) for x in rewards.tolist()],
        "runtime_judge": _lookup(runtime_resp, "judge"),
        "winner_miner_index": _lookup(runtime_resp, "winner_miner_index"),
        "timing_ms": {"total": elapsed_ms, "dendrite_call": call_ms},
    }


async def run_math_probe(**kwargs: Any) -> dict[str, Any]:
    return await run_navigation_probe(**kwargs)
