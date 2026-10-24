# Reliability Evaluation Post-Mortem (20 Fresh Celesto Sandboxes)

## 1. Executive Summary
- **Total Fresh Sandboxes Evaluated (`run_count`)**: 20
- **End-to-End Success Rate (`success_rate`)**: 100.0% (20/20)
- **Median Wall-Clock Time (`median_wall_clock_s`)**: 5.4457s
- **90th Percentile Wall-Clock Time (`p90_wall_clock_s`)**: 9.37s
- **Median Sandbox Boot-to-Ready Time (`median_boot_to_ready_s`)**: 2.9355s
- **Total Compute Cost (`total_cost_usd`)**: $0.002000 USD

## 2. Failure Modes Observed & Mitigations Engineered
During initial development and evaluation of the 10-step Job Hunt Desk pipeline on Celesto Cloud, three concrete infrastructure and guest-environment failure modes surfaced:

1. **Cloud Trial Retention & Per-Minute API Rate Quotas (`HTTP 429 Too Many Requests`)**:
   - **Root Cause**: Firing a 5-job concurrency burst plus repeated `computer.list` status polls triggered Celesto Cloud's per-minute request rate limiter (`HTTP 429: The server is limiting requests`), while the trial also enforces a 1-retained-sandbox cap.
   - **Mitigation**: Eliminated unnecessary pre-boot list polling during normal sequential teardown, added a 4-second inter-run pacing window, and implemented a 15s/30s/45s cooldown backoff when HTTP 429 rate limiting is returned.

2. **Asynchronous Stop/Start State Transition (`HTTP 409 Conflict`)**:
   - **Root Cause**: Calling `exec` immediately after `celesto computer start` hit HTTP 409 because the remote microVM was still transitioning from `starting` to `running`.
   - **Mitigation**: Added `_exec_with_retry()` with exponential backoff in `CelestoSandboxSession`.

3. **Minimal Guest Image Runtime Footprint (`/bin/sh: python3: not found`)**:
   - **Root Cause**: The default cloud `scratch` microVM image boots rapidly with POSIX `/bin/sh`, `awk`, and `sha256sum` rather than a heavy Python installation.
   - **Mitigation**: Engineered the 10-step guest pipeline using native POSIX utilities (`awk`, `sha256sum`, `printf`, `test`), eliminating package installation latency and improving reliability.

## 3. Run-by-Run Failure Log
- Zero unrecovered task failures occurred during the 20-run batch after adding rate-limit backoff and HTTP 409 readiness polling.
