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

ALLOWED_OPS = ("+", "-", "*")


class NavigationSynapse(bt.Synapse):
    """
    Navigation-shaped wire envelope for subnet-navigation.

    Primary contract:
    - validator sends a navigation task (`task_kind`, `scene_id`, `goal`, `constraints`);
    - miner returns a route / action proposal in `proposal`;
    - validator submits miner proposals to navigation-runtime and stores the scoring envelope
      (`score`, `score_components`, `score_reason`) returned by that verifier.

    Compatibility only:
    - legacy scalar fields (`operand_a`, `operand_b`, `op`, `result`) remain available so
      old callers do not fail hard;
    - new validator / probe flows should not depend on the scalar path as their primary mode.
    """

    request_id: typing.Optional[str] = None
    task_kind: str = "goal-conditioned-navigation"
    scene_id: typing.Optional[str] = None
    map_id: typing.Optional[str] = None
    start: typing.Optional[typing.Dict[str, typing.Any]] = None
    goal: typing.Optional[typing.Dict[str, typing.Any]] = None
    constraints: typing.Optional[typing.Dict[str, typing.Any]] = None
    context: typing.Optional[typing.Dict[str, typing.Any]] = None

    proposal: typing.Optional[typing.Dict[str, typing.Any]] = None
    score: typing.Optional[float] = None
    score_components: typing.Optional[typing.Dict[str, float]] = None
    score_reason: typing.Optional[str] = None

    # Legacy scalar quiz fields kept for the current simplified runtime.
    operand_a: typing.Optional[int] = None
    operand_b: typing.Optional[int] = None
    op: typing.Optional[str] = None
    result: typing.Optional[float] = None

    def deserialize(self) -> typing.Any:
        if self.result is not None:
            return self.result
        if self.score is not None:
            return self.score
        return self.proposal


# Deprecated compatibility alias.
MathSynapse = NavigationSynapse
