# Subnet SLAM

`subnet-slam` is the chain-facing shim for the `semantic-slam` beta track.

## Contract shape

- Validator sends `SlamJobSynapse` with `job_id`, `source_type`,
  `input_manifest_url`, `holdout_policy_id`, `deadline_ms`,
  `validator_nonce`.
- Miner/runtime returns `artifact_manifest`, `preview_url`, `runtime_stats`.
- Validator attaches explicit `score`, `score_components`, `score_reason`
  and converts them into on-chain weight signals.

## Runtime boundary

- Internal runtime lives outside this repo in
  `sources/semantic-slam/services/slam-runtime`.
- This shim calls that runtime through `KONNEX_SLAM_RUNTIME_BASE_URL`.
- If the runtime is unavailable, miner/validator fall back to a local
  artifact-presence stub so localnet bring-up still works.
