# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# Copyright © 2023 Opentensor Foundation

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

import asyncio
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from neurons.validator import Validator
from template.protocol import NavigationSynapse
from template.utils.uids import get_random_uids
from template.validator.reward import get_rewards


class TemplateValidatorNeuronTestCase(unittest.TestCase):
    def setUp(self):
        sys.argv = [sys.argv[0]]
        config = Validator.config()
        config.mock = True
        if config.wallet is None:
            config.wallet = SimpleNamespace()
        if config.metagraph is None:
            config.metagraph = SimpleNamespace()
        if config.subtensor is None:
            config.subtensor = SimpleNamespace()
        config.wallet._mock = True
        config.metagraph._mock = True
        config.subtensor._mock = True
        config.neuron.axon_off = True
        config.neuron.disable_set_weights = True
        config.neuron.num_concurrent_forwards = 1
        config.neuron.sample_size = 4
        config.neuron.runtime_base_url = ""
        self.neuron = Validator(config)
        self.miner_uids = get_random_uids(self.neuron, k=4)

    def test_dummy_responses_are_navigation_proposals(self):
        synapse = NavigationSynapse(
            request_id="test-navigation-query",
            task_kind="goal-conditioned-navigation",
            scene_id="test-scene",
            map_id="test-map",
            start={"kind": "origin", "coordinates": {"x": 0, "y": 0}},
            goal={"instruction": "Move toward the highlighted checkpoint."},
            constraints={"preferred_motion_kind": "discrete"},
        )

        responses = self.neuron.dendrite.query(
            axons=[self.neuron.metagraph.axons[uid] for uid in self.miner_uids],
            synapse=synapse,
            deserialize=False,
        )

        for response in responses:
            self.assertIsInstance(response.proposal, dict)
            self.assertIn("action_id", response.proposal)
            self.assertIn("motion_kind", response.proposal)
            self.assertIsNone(response.result)

    def test_navigation_rewards_normalize_explicit_scores(self):
        responses = [
            SimpleNamespace(score=0.2),
            SimpleNamespace(score=0.8),
            SimpleNamespace(score=0.0),
        ]

        rewards = get_rewards(self.neuron, expected=None, responses=responses)

        self.assertTrue(np.allclose(rewards, np.array([0.2, 0.8, 0.0], dtype=np.float32)))
        self.assertAlmostEqual(float(np.sum(rewards)), 1.0, places=6)

    def test_legacy_reward_fallback_still_works(self):
        rewards = get_rewards(
            self.neuron,
            expected=10.0,
            responses=[10.0, 12.0, None],
        )

        self.assertTrue(np.allclose(rewards, np.array([1.0, 0.0, 0.0], dtype=np.float32)))

    def test_forward_updates_scores_via_navigation_path(self):
        before = np.array(self.neuron.scores, copy=True)

        with patch("template.validator.forward.time.sleep", return_value=None):
            asyncio.run(self.neuron.forward())

        after = self.neuron.scores
        self.assertEqual(after.shape, before.shape)
        self.assertGreater(float(np.sum(after)), float(np.sum(before)))


if __name__ == "__main__":
    unittest.main()
