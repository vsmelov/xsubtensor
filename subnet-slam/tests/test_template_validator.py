# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# Copyright © 2023 Opentensor Foundation

import unittest

import numpy as np

from template.protocol import ALLOWED_SOURCE_TYPES, SlamJobSynapse
from template.validator.reward import get_rewards


class TemplateValidatorNeuronTestCase(unittest.TestCase):
    def test_deserialize_prefers_preview_url(self):
        synapse = SlamJobSynapse(source_type="stray", preview_url="https://example/preview")
        self.assertEqual(synapse.deserialize(), "https://example/preview")

    def test_reward_prefers_explicit_scores(self):
        responses = [
            SlamJobSynapse(source_type="stray", score=0.6, preview_url="https://example/a"),
            SlamJobSynapse(source_type="ue", score=0.4, preview_url="https://example/b"),
        ]
        rewards = get_rewards(None, responses=responses)
        self.assertAlmostEqual(float(rewards[0]), 0.6, places=5)
        self.assertAlmostEqual(float(rewards[1]), 0.4, places=5)

    def test_reward_uses_artifact_presence_fallback(self):
        responses = [
            SlamJobSynapse(source_type=ALLOWED_SOURCE_TYPES[0], preview_url="https://example/a"),
            SlamJobSynapse(source_type=ALLOWED_SOURCE_TYPES[1], preview_url="https://example/b"),
        ]
        rewards = get_rewards(None, responses=responses)
        self.assertAlmostEqual(float(np.sum(rewards)), 1.0, places=5)
        self.assertTrue(np.all(rewards > 0))

    def test_reward_all_none(self):
        rewards = get_rewards(None, responses=[SlamJobSynapse(), SlamJobSynapse()])
        self.assertEqual(float(np.sum(rewards)), 0.0)
