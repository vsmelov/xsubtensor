# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# Copyright © 2023 <your name>

import typing

import bittensor as bt


ALLOWED_SOURCE_TYPES: typing.Tuple[str, ...] = ("stray", "airsim", "ue")
BETA_PROTOCOL_VERSION = "semantic-slam-beta-v1"
DEFAULT_HOLDOUT_POLICY_ID = "random-100-of-1000-v1"
DEFAULT_INPUT_MANIFEST_URL = "https://example.com/semantic-slam/input-manifest.json"


def normalize_source_type(source_type: typing.Optional[str]) -> str:
    if source_type is None:
        return ""
    return str(source_type).strip().lower()


def is_allowed_source_type(source_type: str) -> bool:
    return normalize_source_type(source_type) in ALLOWED_SOURCE_TYPES


class SlamJobSynapse(bt.Synapse):
    """
    Chain-facing shim for the semantic-slam beta contract.

    The validator sends a reconstruction job envelope and miners return an
    artifact manifest plus optional preview pointer. Validator scoring is
    attached through the explicit score fields.
    """

    job_id: typing.Optional[str] = None
    protocol_version: str = BETA_PROTOCOL_VERSION
    dataset_id: typing.Optional[str] = None
    input_frameset: typing.Optional[str] = None
    task_type: str = "reconstruct_and_render"
    source_type: str = "stray"
    input_manifest_url: str = DEFAULT_INPUT_MANIFEST_URL
    camera_metadata: typing.Optional[typing.Dict[str, typing.Any]] = None
    holdout_policy_id: str = DEFAULT_HOLDOUT_POLICY_ID
    deadline_ms: typing.Optional[int] = None
    validator_nonce: typing.Optional[str] = None

    artifact_manifest: typing.Optional[typing.Dict[str, typing.Any]] = None
    runtime_stats: typing.Optional[typing.Dict[str, typing.Any]] = None
    explain: typing.Optional[str] = None
    preview_url: typing.Optional[str] = None
    verdict: typing.Optional[str] = None
    score: typing.Optional[float] = None
    score_components: typing.Optional[typing.Dict[str, float]] = None
    score_reason: typing.Optional[str] = None

    def deserialize(self) -> typing.Any:
        if self.score is not None:
            return self.score
        if self.preview_url is not None:
            return self.preview_url
        return self.artifact_manifest
