# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# Copyright © 2023 <your name>

import typing

import bittensor as bt
import numpy as np


def _coerce_float(value: typing.Any) -> typing.Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _lookup(obj: typing.Any, key: str) -> typing.Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _extract_score(response: typing.Any) -> typing.Optional[float]:
    direct = _coerce_float(_lookup(response, "score"))
    if direct is not None:
        return max(0.0, direct)
    scoring = _lookup(response, "scoring")
    return _coerce_float(_lookup(scoring, "score"))


def _has_artifact(response: typing.Any) -> bool:
    preview_url = _lookup(response, "preview_url")
    if preview_url:
        return True
    artifact_manifest = _lookup(response, "artifact_manifest")
    return isinstance(artifact_manifest, dict) and bool(artifact_manifest.get("public_url"))


def get_rewards(
    self,
    expected: typing.Optional[float] = None,
    responses: typing.Optional[typing.List[typing.Any]] = None,
) -> np.ndarray:
    responses = list(responses or [])
    n = len(responses)
    if n == 0:
        return np.array([], dtype=np.float32)

    scores = np.full(n, np.nan, dtype=np.float64)
    has_explicit = False
    for i, response in enumerate(responses):
        score = _extract_score(response)
        if score is None or not np.isfinite(score):
            continue
        scores[i] = score
        has_explicit = True

    if has_explicit:
        total = float(np.nansum(scores))
        if total <= 0.0:
            bt.logging.warning("Semantic-SLAM scores were present but non-positive.")
            return np.zeros(n, dtype=np.float32)
        return np.nan_to_num(scores / total, nan=0.0).astype(np.float32)

    weights = np.array([1.0 if _has_artifact(response) else 0.0 for response in responses], dtype=np.float64)
    total = float(np.sum(weights))
    if total <= 0.0:
        bt.logging.warning("No valid semantic-slam artifacts for reward.")
        return np.zeros(n, dtype=np.float32)
    return (weights / total).astype(np.float32)
