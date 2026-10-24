from datetime import datetime
import json
import math
from pathlib import Path
import re
import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
LOGS = ROOT / "logs"
SANDBOX_RE = re.compile(r"^sbx-[a-z0-9]{8,}$")


def _check_iso8601(ts: str) -> None:
    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert parsed is not None


def test_req1_compose_and_seeds():
    compose_text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "api:" in compose_text
    assert "ledger:" in compose_text
    assert "8080:8080" in compose_text
    assert "/docker-entrypoint-initdb.d" in compose_text
    assert "pg_isready" in compose_text
    assert "http://localhost:8080/health" in compose_text
    for key in ("interval:", "timeout:", "retries:", "start_period:"):
        assert compose_text.count(key) >= 2, f"Missing {key} in healthchecks"

    seed_sql = (ROOT / "seeds" / "01_runs.sql").read_text(encoding="utf-8")
    assert "sbx-seeddemo1" in seed_sql
    assert "deleted" in seed_sql
    assert "celesto_sandbox" in seed_sql
    assert "ON CONFLICT" in seed_sql


def test_req2_env_example_and_no_dot_env():
    env_example = ROOT / ".env.example"
    assert env_example.exists(), ".env.example must exist"
    text = env_example.read_text(encoding="utf-8")
    for required_key in (
        "CELESTO_PROVIDER=",
        "CELESTO_API_KEY=",
        "LLM_API_KEY=",
        "LLM_MODEL=",
        "DATABASE_URL=",
        "API_PORT=",
    ):
        assert required_key in text, f"Missing {required_key} in .env.example"
    assert not (ROOT / ".env").exists(), ".env must not be present at repository root"


def test_req3_problem_json():
    data = json.loads((REPORTS / "problem.json").read_text(encoding="utf-8"))
    assert len(data["who"]) >= 40
    assert len(data["agent_work"]) >= 40
    assert len(data["proof_output"]) >= 20
    assert data["idea_source"] in ("idea_bank", "original")


def test_req4_commands_jsonl():
    cmd_log = LOGS / "commands.jsonl"
    assert cmd_log.exists(), "logs/commands.jsonl must exist"
    lines = [l for l in cmd_log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) >= 1
    for line in lines:
        obj = json.loads(line)
        _check_iso8601(obj["ts"])
        assert SANDBOX_RE.match(obj["sandbox_name"])
        assert isinstance(obj["command"], str) and len(obj["command"].strip()) > 0
        assert obj["decision"] in ("allow", "block")
        assert obj["execution_target"] == "celesto_sandbox"


def test_req5_capabilities_json():
    allowed_ids = {
        "persistence",
        "snapshots",
        "celestofs",
        "browser",
        "published_ports",
        "network_policy",
        "safety_hooks",
        "host_mounts",
        "coding_agent_preset",
        "agentor_durable",
    }
    data = json.loads((REPORTS / "capabilities.json").read_text(encoding="utf-8"))
    caps = data["capabilities"]
    assert len(caps) >= 2
    seen_ids = set()
    for c in caps:
        cid = c["id"]
        assert cid in allowed_ids
        assert cid not in seen_ids, f"Duplicate capability id {cid}"
        seen_ids.add(cid)
        assert len(c["why"]) >= 80
        assert (ROOT / c["evidence_path"]).exists(), f"Missing {c['evidence_path']}"


def test_req6_lifecycle_json():
    data = json.loads((REPORTS / "lifecycle.json").read_text(encoding="utf-8"))
    assert data["cleanup_on_success"] is True
    assert data["cleanup_on_failure"] is True
    assert data["cleanup_on_interrupt"] is True
    names = data["sandbox_names"]
    assert len(names) >= 1

    cmd_names = {
        json.loads(line)["sandbox_name"]
        for line in (LOGS / "commands.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    rel_names = {
        r["sandbox_name"]
        for r in json.loads((REPORTS / "reliability.json").read_text(encoding="utf-8"))["runs"]
    }
    known_names = cmd_names | rel_names
    for n in names:
        assert SANDBOX_RE.match(n)
        assert n in known_names, f"{n} not found in commands.jsonl or reliability.json"


def test_req7_reliability_json_and_postmortem():
    data = json.loads((REPORTS / "reliability.json").read_text(encoding="utf-8"))
    runs = data["runs"]
    n = data["run_count"]
    assert n == len(runs) and n >= 20

    seen = set()
    for r in runs:
        name = r["sandbox_name"]
        assert SANDBOX_RE.match(name)
        assert name not in seen, f"Duplicate sandbox_name {name}"
        seen.add(name)
        assert r["fresh"] is True
        assert isinstance(r["success"], bool)
        assert r["wall_clock_s"] > 0
        assert r["boot_to_ready_s"] > 0
        assert r["cost_usd"] >= 0

    expected_sr = sum(1 for r in runs if r["success"]) / n
    assert abs(data["success_rate"] - expected_sr) <= 0.001

    walls = sorted(float(r["wall_clock_s"]) for r in runs)
    boots = sorted(float(r["boot_to_ready_s"]) for r in runs)
    mid = n // 2
    expected_med_wall = (walls[mid - 1] + walls[mid]) / 2.0 if n % 2 == 0 else walls[mid]
    expected_med_boot = (boots[mid - 1] + boots[mid]) / 2.0 if n % 2 == 0 else boots[mid]
    expected_p90_wall = walls[math.ceil(0.90 * n) - 1]
    expected_cost = sum(float(r["cost_usd"]) for r in runs)

    assert abs(data["median_wall_clock_s"] - expected_med_wall) <= 0.001
    assert abs(data["p90_wall_clock_s"] - expected_p90_wall) <= 0.001
    assert abs(data["median_boot_to_ready_s"] - expected_med_boot) <= 0.001
    assert abs(data["total_cost_usd"] - expected_cost) <= 0.001

    pm_path = ROOT / data["postmortem_path"]
    assert pm_path.exists()
    assert len(pm_path.read_text(encoding="utf-8").strip()) >= 200


def test_req8_containment_json():
    data = json.loads((REPORTS / "containment.json").read_text(encoding="utf-8"))
    assert data["attack"] in (
        "prompt_injection_exfil",
        "destructive_command",
        "suspicious_package",
    )
    assert data["blocked"] is True
    assert data["host_untouched"] is True
    assert len(data["evidence_paths"]) >= 1
    for p in data["evidence_paths"]:
        assert (ROOT / p).exists()


def test_req9_failure_policy_and_trace():
    data = json.loads((REPORTS / "failure_policy.json").read_text(encoding="utf-8"))
    assert data["failed_step"] == 7
    assert data["total_steps"] == 10
    assert data["policy"] in ("resume", "rollback", "fresh")
    assert len(data["rationale"]) >= 200
    trace_file = ROOT / data["trace_path"]
    assert trace_file.exists()
    events = [
        json.loads(line)
        for line in trace_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(
        e.get("event") == "policy_applied" and e.get("policy") == data["policy"]
        for e in events
    )


def test_req10_concurrency_json():
    data = json.loads((REPORTS / "concurrency.json").read_text(encoding="utf-8"))
    jobs = data["jobs"]
    assert len(jobs) >= 5
    seen = set()
    for j in jobs:
        name = j["sandbox_name"]
        assert SANDBOX_RE.match(name)
        assert name not in seen
        seen.add(name)
        _check_iso8601(j["started_at"])
    assert len(data["breakage_notes"]) >= 40


def test_req11_run_ledger_http_api():
    base_url = "http://localhost:8080"
    with httpx.Client(base_url=base_url, timeout=5.0) as client:
        r_health = client.get("/health")
        assert r_health.status_code == 200
        assert r_health.json() == {"status": "ok"}

        r_runs = client.get("/api/runs")
        assert r_runs.status_code == 200
        runs_list = r_runs.json()
        assert any(r["sandbox_name"] == "sbx-seeddemo1" for r in runs_list)

        valid_payload = {
            "run_id": "run-pytest-valid01",
            "sandbox_name": "sbx-pytestval01",
            "problem_id": "job-hunt-desk",
            "state": "deleted",
            "execution_target": "celesto_sandbox",
        }
        r_post_ok = client.post("/api/runs", json=valid_payload)
        assert r_post_ok.status_code == 201
        assert r_post_ok.json()["sandbox_name"] == "sbx-pytestval01"

        bad_payload = {
            "run_id": "run-pytest-bad01",
            "sandbox_name": "sbx-pytestbad01",
            "problem_id": "job-hunt-desk",
            "state": "created",
            "execution_target": "host",
        }
        r_post_bad = client.post("/api/runs", json=bad_payload)
        assert r_post_bad.status_code == 400
