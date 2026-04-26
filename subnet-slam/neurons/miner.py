# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# Copyright © 2023 <your name>

import time
import typing
import uuid

import bittensor as bt

import template
from template.base.miner import BaseMinerNeuron
from template.protocol import (
    BETA_PROTOCOL_VERSION,
    DEFAULT_HOLDOUT_POLICY_ID,
    DEFAULT_INPUT_MANIFEST_URL,
    SlamJobSynapse,
    is_allowed_source_type,
    normalize_source_type,
)
from template.runtime_client import runtime_base_url, runtime_timeout, try_post_json


def _fallback_payload(
    synapse: SlamJobSynapse,
    source_type: str,
    req_id: str,
    timeout_s: float,
) -> dict[str, typing.Any]:
    job_id = synapse.job_id or f"slam-job-{req_id}"
    dataset_id = f"{source_type}-staging-dataset"
    return {
        "protocol_version": BETA_PROTOCOL_VERSION,
        "job_id": job_id,
        "dataset_id": dataset_id,
        "input_frameset": f"{dataset_id}-frameset",
        "task_type": "reconstruct_and_render",
        "source_type": source_type,
        "input_manifest_url": synapse.input_manifest_url or DEFAULT_INPUT_MANIFEST_URL,
        "camera_metadata": synapse.camera_metadata,
        "holdout_policy_id": synapse.holdout_policy_id or DEFAULT_HOLDOUT_POLICY_ID,
        "deadline_ms": int(synapse.deadline_ms or timeout_s * 1000),
        "validator_nonce": synapse.validator_nonce or job_id,
    }


def _apply_submission(
    synapse: SlamJobSynapse,
    payload: dict[str, typing.Any],
    runtime_resp: dict[str, typing.Any] | None,
    req_id: str,
) -> SlamJobSynapse:
    synapse.job_id = str(payload["job_id"])
    synapse.protocol_version = BETA_PROTOCOL_VERSION
    synapse.dataset_id = str(payload["dataset_id"])
    synapse.input_frameset = str(payload["input_frameset"])
    synapse.task_type = str(payload["task_type"])
    synapse.source_type = str(payload["source_type"])
    synapse.input_manifest_url = str(payload["input_manifest_url"])
    synapse.camera_metadata = payload.get("camera_metadata")
    synapse.holdout_policy_id = str(payload["holdout_policy_id"])
    synapse.deadline_ms = int(payload["deadline_ms"])
    synapse.validator_nonce = str(payload["validator_nonce"])

    if isinstance(runtime_resp, dict):
        synapse.artifact_manifest = runtime_resp.get("artifact_manifest")
        synapse.runtime_stats = runtime_resp.get("runtime_stats")
        synapse.explain = runtime_resp.get("explain")
        artifact_manifest = synapse.artifact_manifest or {}
        if isinstance(artifact_manifest, dict) and artifact_manifest.get("public_url"):
            synapse.preview_url = str(artifact_manifest["public_url"])
            return synapse

    synapse.artifact_manifest = {
        "artifact_id": f"slam-{req_id}",
        "artifact_type": "mesh_bundle",
        "title": f"Fallback semantic-slam artifact for {synapse.source_type}",
        "public_url": synapse.input_manifest_url,
        "metadata": {
            "source_type": synapse.source_type,
            "holdout_policy_id": synapse.holdout_policy_id,
        },
    }
    synapse.runtime_stats = {
        "mode": "fallback_stub",
        "input_manifest_url": synapse.input_manifest_url,
    }
    synapse.explain = "Fell back to local semantic-slam shim stub because runtime response was unavailable."
    synapse.preview_url = synapse.input_manifest_url
    return synapse


class Miner(BaseMinerNeuron):
    def __init__(self, config=None):
        super(Miner, self).__init__(config=config)

    async def forward(self, synapse: template.protocol.SlamJobSynapse) -> template.protocol.SlamJobSynapse:
        source_type = normalize_source_type(synapse.source_type)
        if not is_allowed_source_type(source_type):
            synapse.preview_url = None
            bt.logging.warning(f"Unsupported semantic-slam source_type {synapse.source_type!r}")
            return synapse

        req_id = str(uuid.uuid4())[:8]
        t0 = time.monotonic()
        payload = _fallback_payload(synapse, source_type, req_id, runtime_timeout(self.config))
        runtime_resp = try_post_json(
            runtime_base_url(self.config),
            "/internal/mine",
            payload,
            runtime_timeout(self.config),
        )
        synapse = _apply_submission(synapse, payload, runtime_resp, req_id)
        dt_s = time.monotonic() - t0
        bt.logging.info(
            f"Semantic-SLAM shim [{req_id}] artifact ready after {dt_s:.2f}s "
            f"source_type={source_type} preview_url={synapse.preview_url}"
        )
        return synapse

    async def blacklist(self, synapse: template.protocol.SlamJobSynapse) -> typing.Tuple[bool, str]:
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            bt.logging.warning("Received a request without a dendrite or hotkey.")
            return True, "Missing dendrite or hotkey"

        uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
        if (
            not self.config.blacklist.allow_non_registered
            and synapse.dendrite.hotkey not in self.metagraph.hotkeys
        ):
            bt.logging.trace(f"Blacklisting un-registered hotkey {synapse.dendrite.hotkey}")
            return True, "Unrecognized hotkey"

        if self.config.blacklist.force_validator_permit:
            if not self.metagraph.validator_permit[uid]:
                bt.logging.warning(
                    f"Blacklisting a request from non-validator hotkey {synapse.dendrite.hotkey}"
                )
                return True, "Non-validator hotkey"

        bt.logging.trace(f"Not Blacklisting recognized hotkey {synapse.dendrite.hotkey}")
        return False, "Hotkey recognized!"

    async def priority(self, synapse: template.protocol.SlamJobSynapse) -> float:
        if synapse.dendrite is None or synapse.dendrite.hotkey is None:
            bt.logging.warning("Received a request without a dendrite or hotkey.")
            return 0.0

        caller_uid = self.metagraph.hotkeys.index(synapse.dendrite.hotkey)
        priority = float(self.metagraph.S[caller_uid])
        bt.logging.trace(f"Prioritizing {synapse.dendrite.hotkey} with value: {priority}")
        return priority


if __name__ == "__main__":
    with Miner() as miner:
        while True:
            bt.logging.info(f"Miner running... {time.time()}")
            time.sleep(5)
