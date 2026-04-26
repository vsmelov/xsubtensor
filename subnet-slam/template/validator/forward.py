from __future__ import annotations

# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# Copyright © 2023 <your name>

import json
import time

import bittensor as bt

from template.protocol import (
    ALLOWED_SOURCE_TYPES,
    DEFAULT_HOLDOUT_POLICY_ID,
    DEFAULT_INPUT_MANIFEST_URL,
    SlamJobSynapse,
)
from template.runtime_client import runtime_base_url, runtime_timeout, try_post_json
from template.validator.reward import get_rewards
from template.utils.uids import get_random_uids


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


def _build_slam_synapse(step: int, timeout_s: float) -> SlamJobSynapse:
    source_type = ALLOWED_SOURCE_TYPES[step % len(ALLOWED_SOURCE_TYPES)]
    return SlamJobSynapse(
        job_id=f"slam-job-{step}",
        source_type=source_type,
        input_manifest_url=DEFAULT_INPUT_MANIFEST_URL,
        camera_metadata={"scene_id": f"stray-scene-{step % 4}", "step_index": step},
        holdout_policy_id=DEFAULT_HOLDOUT_POLICY_ID,
        deadline_ms=int(timeout_s * 1000),
        validator_nonce=f"slam-round-{step}",
    )


def _preview_url(response) -> str | None:
    value = _lookup(response, "preview_url")
    if value:
        return str(value)
    artifact_manifest = _lookup(response, "artifact_manifest")
    if isinstance(artifact_manifest, dict) and artifact_manifest.get("public_url"):
        return str(artifact_manifest["public_url"])
    return None


def _fallback_score(response) -> tuple[float, dict[str, float], str]:
    preview_url = _preview_url(response)
    if not preview_url:
        return 0.0, {
            "overall": 0.0,
            "holdout_quality": 0.0,
            "depth_quality": 0.0,
            "artifact_integrity": 0.0,
        }, "missing artifact"
    overall = 0.72
    return overall, {
        "overall": overall,
        "holdout_quality": 0.74,
        "depth_quality": 0.71,
        "artifact_integrity": 0.88,
    }, "local semantic-slam fallback heuristic"


def _runtime_payload(synapse: SlamJobSynapse) -> dict:
    source_type = str(synapse.source_type or "stray").lower()
    dataset_id = synapse.dataset_id or f"{source_type}-staging-dataset"
    input_frameset = synapse.input_frameset or f"{dataset_id}-frameset"
    return {
        "protocol_version": synapse.protocol_version,
        "job_id": synapse.job_id,
        "dataset_id": dataset_id,
        "input_frameset": input_frameset,
        "task_type": synapse.task_type or "reconstruct_and_render",
        "source_type": synapse.source_type,
        "input_manifest_url": synapse.input_manifest_url,
        "camera_metadata": synapse.camera_metadata,
        "holdout_policy_id": synapse.holdout_policy_id,
        "deadline_ms": synapse.deadline_ms,
        "validator_nonce": synapse.validator_nonce,
    }


def _runtime_score(response, runtime_verdict: dict) -> tuple[float, dict[str, float], str]:
    base = _coerce_float(runtime_verdict.get("overall")) or 0.0
    if not _preview_url(response):
        base = 0.0
    overall = round(base, 4)
    return overall, {
        "overall": overall,
        "holdout_quality": round(_coerce_float(runtime_verdict.get("holdout_quality")) or 0.0, 4),
        "depth_quality": round(_coerce_float(runtime_verdict.get("depth_quality")) or 0.0, 4),
        "artifact_integrity": round(_coerce_float(runtime_verdict.get("artifact_integrity")) or 0.0, 4),
    }, str(runtime_verdict.get("explain") or runtime_verdict.get("verdict") or "runtime verifier")


async def forward(self):
    miner_uids = get_random_uids(self, k=self.config.neuron.sample_size)
    synapse = _build_slam_synapse(int(self.step), runtime_timeout(self.config))

    responses = await self.dendrite(
        axons=[self.metagraph.axons[uid] for uid in miner_uids],
        synapse=synapse,
        deserialize=False,
    )

    runtime_verdict = try_post_json(
        runtime_base_url(self.config),
        "/internal/verify",
        _runtime_payload(synapse),
        runtime_timeout(self.config),
    )

    response_rows: list[dict] = []
    for response in responses:
        if isinstance(runtime_verdict, dict):
            score, components, reason = _runtime_score(response, runtime_verdict)
            response.verdict = runtime_verdict.get("verdict")
        else:
            score, components, reason = _fallback_score(response)
            response.verdict = "partial" if score > 0 else "failed"
        response.score = score
        response.score_components = components
        response.score_reason = reason
        response_rows.append(
            {
                "preview_url": _preview_url(response),
                "artifact_manifest": _lookup(response, "artifact_manifest"),
                "score": round(float(score), 4),
                "components": components,
                "verdict": _lookup(response, "verdict"),
                "reason": reason,
            }
        )

    rewards = get_rewards(self, responses=responses)
    scoreboard = {
        "mode": "semantic-slam",
        "job_id": synapse.job_id,
        "source_type": synapse.source_type,
        "holdout_policy_id": synapse.holdout_policy_id,
        "uids": [int(u) for u in miner_uids],
        "responses": response_rows,
        "rewards": [float(x) for x in rewards.tolist()],
        "runtime_verdict": runtime_verdict,
    }
    bt.logging.info("SLAM_SCOREBOARD " + json.dumps(scoreboard))

    self.update_scores(rewards, miner_uids)
    time.sleep(float(self.config.neuron.forward_sleep))
