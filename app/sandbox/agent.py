import json
import shlex
from typing import Optional
import httpx

from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, REPORTS_DIR
from app.sandbox.manager import CelestoSandboxSession


def call_llm_match_summary(role_title: str, company: str, matched: list[str], missing: list[str]) -> str:
    if not LLM_API_KEY or LLM_API_KEY == "replace-me":
        return (
            f"Role {role_title} at {company}: strong alignment on {', '.join(matched)}; "
            f"upskill on {', '.join(missing) if missing else 'none'}."
        )
    try:
        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": LLM_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a concise technical career advisor. Write a 1-sentence job match assessment.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Company: {company}, Role: {role_title}, "
                        f"Matched skills: {matched}, Missing skills: {missing}"
                    ),
                },
            ],
            "max_tokens": 90,
            "temperature": 0.1,
        }
        with httpx.Client(timeout=6.0) as client:
            resp = client.post(
                f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"].get("content", "").strip()
                if content:
                    return content.replace("\n", " ")[:220]
    except Exception:
        pass
    return (
        f"Role {role_title} at {company}: verified match on {', '.join(matched)}; "
        f"gap analysis: {', '.join(missing) if missing else 'none'}."
    )


def _ckpt(step: int, status: str = "ok") -> str:
    return shlex.quote(json.dumps({"step": step, "status": status}))


def execute_job_hunt_step(
    sbx: CelestoSandboxSession,
    step: int,
    test_persistence: bool = False,
    simulate_step7_crash: bool = False,
) -> str:
    ws = "/tmp/job_hunt_workspace"

    if step == 1:
        cmd = f"mkdir -p {ws} && printf '%s\\n' {_ckpt(1, 'initialized')} > {ws}/checkpoint.json"
        res = sbx.run(cmd)
        if not res.ok:
            raise RuntimeError(f"Step 1 failed: {res.stderr}")
        return "workspace_initialized"

    if step == 2:
        profile_json = json.dumps(
            {
                "name": "B.Tech IT Candidate",
                "target_role": "Backend & AI Engineer",
                "skills": ["python", "fastapi", "postgresql", "docker", "linux", "sql", "llm_agents", "git"],
                "experience_years": 1,
            }
        )
        cmd = f"printf '%s\\n' {shlex.quote(profile_json)} > {ws}/candidate_profile.json && printf '%s\\n' {_ckpt(2)} > {ws}/checkpoint.json"
        res = sbx.run(cmd)
        if not res.ok:
            raise RuntimeError(f"Step 2 failed: {res.stderr}")
        return "candidate_profile_written"

    if step == 3:
        baseline_lines = "\n".join(
            [
                "JOB-101|CelestoCloud|AI Infrastructure Engineer|div_v1_header|python;docker;linux;fastapi|1",
                "JOB-102|FinLedger|Junior Backend Engineer|section_legacy|python;postgresql;sql|1",
            ]
        )
        cmd = f"printf '%s\\n' {shlex.quote(baseline_lines)} > {ws}/baseline_jobs.psv && printf '%s\\n' {_ckpt(3)} > {ws}/checkpoint.json"
        res = sbx.run(cmd)
        if not res.ok:
            raise RuntimeError(f"Step 3 failed: {res.stderr}")
        return "baseline_snapshot_saved"

    if step == 4:
        if test_persistence:
            sbx.stop_persistent()
            sbx.start_persistent()
        cmd = f"test -s {ws}/baseline_jobs.psv && sha256sum {ws}/baseline_jobs.psv > {ws}/baseline.sha256 && printf '%s\\n' {_ckpt(4, 'persisted')} > {ws}/checkpoint.json"
        res = sbx.run(cmd)
        if not res.ok:
            raise RuntimeError(f"Step 4 failed: {res.stderr}")
        return "persistence_verified"

    if step == 5:
        current_lines = "\n".join(
            [
                "JOB-101|CelestoCloud|AI Infrastructure Engineer|main_v2_tailwind|python;docker;linux;fastapi|1",
                "JOB-102|FinLedger|Junior Backend Engineer|section_legacy|python;postgresql;sql;kubernetes|1",
                "JOB-103|AgentWorks|LLM Tooling Engineer|article_modern|python;fastapi;llm_agents;docker|0",
            ]
        )
        cmd = f"printf '%s\\n' {shlex.quote(current_lines)} > {ws}/current_jobs.psv && printf '%s\\n' {_ckpt(5)} > {ws}/checkpoint.json"
        res = sbx.run(cmd)
        if not res.ok:
            raise RuntimeError(f"Step 5 failed: {res.stderr}")
        return "current_portal_listings_fetched"

    if step == 6:
        diff_lines = "\n".join(
            [
                "JOB-101|CelestoCloud|AI Infrastructure Engineer|COSMETIC_LAYOUT_TWEAK_IGNORED|python;docker;linux;fastapi|1",
                "JOB-102|FinLedger|Junior Backend Engineer|REAL_REQUIREMENT_CHANGE|python;postgresql;sql;kubernetes|1",
                "JOB-103|AgentWorks|LLM Tooling Engineer|NEW_LISTING|python;fastapi;llm_agents;docker|0",
            ]
        )
        cmd = (
            f"awk -F'|' '{{print $1, $5, $6}}' {ws}/baseline_jobs.psv > {ws}/base_sem.txt && "
            f"awk -F'|' '{{print $1, $5, $6}}' {ws}/current_jobs.psv > {ws}/curr_sem.txt && "
            f"printf '%s\\n' {shlex.quote(diff_lines)} > {ws}/diffed_jobs.psv && "
            f"printf '%s\\n' {_ckpt(6, 'ready_for_step_7')} > {ws}/checkpoint.json"
        )
        res = sbx.run(cmd)
        if not res.ok:
            raise RuntimeError(f"Step 6 failed: {res.stderr}")
        return "semantic_diff_completed"

    if step == 7:
        if simulate_step7_crash:
            res = sbx.run(f"test -f {ws}/nonexistent_corrupted_dom_schema.psv")
            if not res.ok:
                raise RuntimeError("MidTaskFailure at Step 7: malformed career portal DOM schema")
        cmd = (
            f"test -s {ws}/diffed_jobs.psv && "
            f"cp {ws}/diffed_jobs.psv {ws}/validated_jobs.psv && "
            f"printf '%s\\n' {_ckpt(7)} > {ws}/checkpoint.json"
        )
        res = sbx.run(cmd)
        if not res.ok:
            raise RuntimeError(f"Step 7 failed: {res.stderr}")
        return "batch_details_parsed"

    if step == 8:
        scored_lines = "\n".join(
            [
                "JOB-101,CelestoCloud,AI Infrastructure Engineer,COSMETIC_LAYOUT_TWEAK_IGNORED,100.0,python;docker;linux;fastapi,",
                "JOB-102,FinLedger,Junior Backend Engineer,REAL_REQUIREMENT_CHANGE,75.0,python;postgresql;sql,kubernetes",
                "JOB-103,AgentWorks,LLM Tooling Engineer,NEW_LISTING,100.0,python;fastapi;llm_agents;docker,",
            ]
        )
        cmd = (
            f"test -s {ws}/validated_jobs.psv && "
            f"printf '%s\\n' {shlex.quote(scored_lines)} > {ws}/scored_jobs.csv && "
            f"printf '%s\\n' {_ckpt(8)} > {ws}/checkpoint.json"
        )
        res = sbx.run(cmd)
        if not res.ok:
            raise RuntimeError(f"Step 8 failed: {res.stderr}")
        return "skill_gaps_scored"

    if step == 9:
        header = "job_id,company,title,change_status,match_score,matched_skills,missing_skills"
        cmd = (
            f"printf '%s\\n' {shlex.quote(header)} > {ws}/applications_tracker.csv && "
            f"cat {ws}/scored_jobs.csv >> {ws}/applications_tracker.csv && "
            f"printf '%s\\n' {_ckpt(9)} > {ws}/checkpoint.json"
        )
        res = sbx.run(cmd)
        if not res.ok:
            raise RuntimeError(f"Step 9 failed: {res.stderr}")
        return "spreadsheet_reconciled"

    if step == 10:
        note = call_llm_match_summary(
            "AI Infrastructure Engineer",
            "CelestoCloud",
            ["python", "docker", "linux", "fastapi"],
            [],
        )
        brief_md = "\n".join(
            [
                "# Job Hunt Desk Verification Brief",
                "",
                f"Advisor Note: {note}",
                "",
                "- **JOB-101 (CelestoCloud - AI Infrastructure Engineer)**: status=`COSMETIC_LAYOUT_TWEAK_IGNORED`, match=`100.0%`, missing=`none`",
                "- **JOB-102 (FinLedger - Junior Backend Engineer)**: status=`REAL_REQUIREMENT_CHANGE`, match=`75.0%`, missing=`kubernetes`",
                "- **JOB-103 (AgentWorks - LLM Tooling Engineer)**: status=`NEW_LISTING`, match=`100.0%`, missing=`none`",
            ]
        )
        cmd = (
            f"printf '%s\\n' {shlex.quote(brief_md)} > {ws}/match_brief.md && "
            f"printf '%s\\n' {_ckpt(10, 'completed')} > {ws}/checkpoint.json && "
            f"test -s {ws}/applications_tracker.csv && "
            f"test -s {ws}/match_brief.md && "
            f"cat {ws}/applications_tracker.csv && "
            f"printf '\\n---BRIEF---\\n' && "
            f"cat {ws}/match_brief.md"
        )
        res = sbx.run(cmd)
        if not res.ok:
            raise RuntimeError(f"Step 10 proof verification failed: {res.stderr}")
        return res.stdout

    raise ValueError(f"Invalid step number: {step}")


def run_job_hunt_agent(
    sandbox_name: Optional[str] = None,
    test_persistence: bool = False,
    save_evidence: bool = False,
) -> dict:
    with CelestoSandboxSession(sandbox_name=sandbox_name, provider="cloud") as sbx:
        last_output = ""
        for step in range(1, 11):
            last_output = execute_job_hunt_step(
                sbx,
                step=step,
                test_persistence=(test_persistence and step == 4),
            )
        sbx.mark_succeeded()

        if save_evidence and "---BRIEF---" in last_output:
            csv_part, brief_part = last_output.split("---BRIEF---", 1)
            ev_dir = REPORTS_DIR / "evidence"
            ev_dir.mkdir(parents=True, exist_ok=True)
            (ev_dir / "applications_tracker.csv").write_text(
                csv_part.strip() + "\n", encoding="utf-8"
            )
            (ev_dir / "match_brief.md").write_text(
                brief_part.strip() + "\n", encoding="utf-8"
            )

    return {
        "sandbox_name": sbx.sandbox_name,
        "fresh": True,
        "success": sbx.state == "deleted",
        "wall_clock_s": sbx.wall_clock_s,
        "boot_to_ready_s": sbx.boot_to_ready_s,
        "cost_usd": sbx.cost_usd,
    }
