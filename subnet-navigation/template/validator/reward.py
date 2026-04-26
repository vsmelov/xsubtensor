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


def _extract_explicit_score(response: typing.Any) -> typing.Optional[float]:
    direct = _coerce_float(_lookup(response, "score"))
    if direct is not None:
        return direct

    scoring = _lookup(response, "scoring")
    scoring_score = _coerce_float(_lookup(scoring, "score"))
    if scoring_score is not None:
        return scoring_score

    components = _lookup(response, "score_components")
    total = _coerce_float(_lookup(components, "total"))
    if total is not None:
        return total

    return None


def _extract_legacy_response_value(response: typing.Any) -> typing.Optional[float]:
    explicit = _coerce_float(response)
    if explicit is not None:
        return explicit
    return _coerce_float(_lookup(response, "result"))


def get_rewards(
    self,
    expected: typing.Optional[float],
    responses: typing.List[typing.Any],
) -> np.ndarray:
    """
    Reward adapter for the staged math-template -> navigation-template migration.

    Preferred navigation path:
    - responses carry an explicit `score` or `scoring.score`;
    - rewards are proportional to the non-negative score mass.

    Current simplified fallback:
    - responses carry only scalar `result`;
    - rewards stay winner-take-all by smallest |response - expected|.
    """
    n = len(responses)

    explicit_scores = np.full(n, np.nan, dtype=np.float64)
    has_explicit_scores = False
    for i, response in enumerate(responses):
        score = _extract_explicit_score(response)
        if score is None or not np.isfinite(score):
            continue
        explicit_scores[i] = max(0.0, float(score))
        has_explicit_scores = True

    if has_explicit_scores:
        total = float(np.nansum(explicit_scores))
        if total <= 0.0:
            bt.logging.warning("Navigation scores were present but non-positive.")
            return np.zeros(n, dtype=np.float32)

        out = np.nan_to_num(explicit_scores / total, nan=0.0).astype(np.float32)
        return out

    if expected is None:
        bt.logging.warning("No explicit navigation scores and no legacy expected value.")
        return np.zeros(n, dtype=np.float32)

    errs = np.full(n, np.inf, dtype=np.float64)
    for i, response in enumerate(responses):
        value = _extract_legacy_response_value(response)
        if value is None:
            continue
        errs[i] = abs(float(value) - float(expected))

    finite = errs[np.isfinite(errs)]
    if finite.size == 0:
        bt.logging.warning("No valid miner responses for reward.")
        return np.zeros(n, dtype=np.float32)

    best = float(np.min(finite))
    winners = np.isfinite(errs) & (errs <= best + 1e-6)
    k = int(np.sum(winners))
    out = np.zeros(n, dtype=np.float32)
    if k > 0:
        out[winners] = 1.0 / k
    return out
