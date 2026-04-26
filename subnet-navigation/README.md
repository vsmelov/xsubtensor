# subnet-navigation

`subnet-navigation` is the navigation-oriented subnet copy inside `sources/xsubtensor`. In this repo it now acts as a real chain-facing shim to `sources/drone-navigation/services/navigation-runtime`.

## Current behavior

- Validators emit `NavigationSynapse`, not math-first quiz traffic.
- Miners answer with navigation proposals and use `navigation-runtime /internal/mine` when `KONNEX_NAV_RUNTIME_BASE_URL` is configured.
- Validators and the HTTP probe submit proposal batches to `navigation-runtime /internal/verify-round` and use the returned `normalized_weight_signals` / judge verdicts as rewards.
- The old scalar fields (`operand_a`, `operand_b`, `op`, `result`) remain only for compatibility with legacy callers.

Example synapse:

```python
NavigationSynapse(
    request_id="nav-step-12",
    task_kind="goal-conditioned-navigation",
    scene_id="localnet-scene-0",
    map_id="localnet-grid",
    start={"kind": "origin", "coordinates": {"x": 0, "y": 0}},
    goal={"instruction": "Move toward the highlighted checkpoint."},
    constraints={"preferred_motion_kind": "discrete", "max_steps": 1},
    context={"mission_reference": "mission-0"},
)
```

## Probe API

- Primary route: `POST /v1/navigation-probe`
- Compatibility alias: `POST /v1/math-probe`
- Health route: `GET /health`

Example request:

```json
{
  "netuid": 4,
  "wallet_name": "nav-val",
  "scene_id": "localnet-dev-scene",
  "map_id": "localnet-grid",
  "goal": {
    "kind": "coordinate_2d",
    "coordinates": { "x": 6, "y": 7 },
    "instruction": "Move toward the safe checkpoint."
  },
  "constraints": {
    "max_steps": 1,
    "timeout_s": 30.0
  }
}
```

Example response shape:

```json
{
  "ok": true,
  "protocol": "subnet-navigation NavigationSynapse",
  "runtime_mode": "navigation-runtime",
  "runtime_base_url": "http://navigation-runtime:8791",
  "request": {
    "task_kind": "goal-conditioned-navigation",
    "goal": { "...": "..." }
  },
  "miners": [
    {
      "uid": 1,
      "proposal": {
        "miner_index": 1,
        "action_id": 9,
        "motion_kind": "world_delta"
      },
      "scoring_envelope": {
        "mode": "navigation-runtime",
        "score": 0.41,
        "components": {
          "overall": 0.82,
          "safety": 0.88,
          "task_match": 0.79,
          "speed": 0.81
        }
      },
      "reward_share": 0.41
    }
  ]
}
```

If `navigation-runtime` is unavailable, the probe and validator fall back to a local navigation-style heuristic scorer. That fallback keeps smoke tests usable but is not the canonical scoring authority.

## Local development

- Compose stack: `docker-compose.subnet-navigation.yml`
- Env example: `.env.subnet-navigation.example`
- Localnet checklist: `../SUBNET_NAVIGATION_LOCALNET.md`
- Shared btcli/localnet flow: `../HOW_TO_CREATE_AND_RUN_SUBNET.md`

Set `KONNEX_NAV_RUNTIME_BASE_URL` before starting the stack:

- `http://host.docker.internal:8791` if `navigation-runtime` runs on the host
- `http://navigation-runtime:8791` if it is attached to the same Docker network

Bring up the stack:

```bash
docker compose -f docker-compose.subnet-navigation.yml \
  --env-file .env.subnet-navigation \
  up -d --build
```

Probe it:

```bash
curl -s http://127.0.0.1:8096/v1/navigation-probe \
  -H 'Content-Type: application/json' \
  -d '{"netuid":4,"wallet_name":"nav-val","goal":{"instruction":"Move toward the safe checkpoint."}}'
```

## Compatibility notes

- `MathSynapse` remains as a deprecated alias to `NavigationSynapse`.
- `get_rewards()` still supports legacy scalar `result` fallback when explicit navigation scores are absent.
- `POST /v1/math-probe` still accepts old payloads, but it is now only a compatibility alias and not the primary path.
