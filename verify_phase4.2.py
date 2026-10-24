python3 -c '
import json, pathlib
from app.sandbox.failure_recovery import run_step7_failure_recovery

report = run_step7_failure_recovery()
print("FAILURE POLICY REPORT:", json.dumps(report, indent=2))

pol = json.loads(pathlib.Path("reports/failure_policy.json").read_text())
assert pol["failed_step"] == 7
assert pol["total_steps"] == 10
assert pol["policy"] in ("resume", "rollback", "fresh")
assert len(pol["rationale"]) >= 200, f"Rationale length {len(pol["rationale"])} < 200"
assert pol["trace_path"] == "reports/failure_trace.jsonl"

trace_lines = [
    json.loads(line)
    for line in pathlib.Path(pol["trace_path"]).read_text().splitlines()
    if line.strip()
]
matched = [
    t for t in trace_lines
    if t.get("event") == "policy_applied" and t.get("policy") == pol["policy"]
]
assert len(matched) >= 1, "Missing policy_applied event in failure_trace.jsonl!"

print("PHASE 4.2 VERIFICATION PASSED! Rationale length:", len(pol["rationale"]))
print("--- reports/failure_trace.jsonl ---")
for line in trace_lines:
    print(json.dumps(line))
'