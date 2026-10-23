import json, pathlib
from app.sandbox.agent import run_job_hunt_agent

result = run_job_hunt_agent(test_persistence=True, save_evidence=True)
print("10-STEP AGENT RUN RESULT:", result)

capabilities_report = {
    "capabilities": [
        {
            "id": "persistence",
            "why": "The Job Hunt Desk agent stops and restarts the sandbox across scraping cycles so baseline job postings, SHA-256 digests, and step checkpoints survive on the guest disk without re-scraping from scratch.",
            "evidence_path": "reports/evidence/applications_tracker.csv"
        },
        {
            "id": "safety_hooks",
            "why": "Untrusted career portals and job descriptions can contain indirect prompt-injection payloads or destructive shell commands; pre-execution Python safety callbacks inspect and block unsafe commands before they reach the guest VM.",
            "evidence_path": "logs/commands.jsonl"
        }
    ]
}

cap_path = pathlib.Path("reports/capabilities.json")
cap_path.write_text(json.dumps(capabilities_report, indent=2) + "\n", encoding="utf-8")

data = json.loads(cap_path.read_text())
assert len(data["capabilities"]) >= 2
for c in data["capabilities"]:
    assert len(c["why"]) >= 80, f"why too short for {c["id"]}"
    assert pathlib.Path(c["evidence_path"]).exists(), f"missing evidence {c["evidence_path"]}"

print("PHASE 3.2 VERIFICATION PASSED! Evidence files created:")
print("--- applications_tracker.csv ---")
print(pathlib.Path("reports/evidence/applications_tracker.csv").read_text())
print("--- match_brief.md ---")
print(pathlib.Path("reports/evidence/match_brief.md").read_text())
