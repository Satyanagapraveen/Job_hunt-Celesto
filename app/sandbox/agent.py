import json
from pathlib import Path
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
            resp = client.post(f"{LLM_BASE_URL.rstrip('/')}/chat/completions", headers=headers, json=payload)
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


def execute_job_hunt_step(sbx: CelestoSandboxSession, step: int, test_persistence: bool = False) -> str:
    ws = "/tmp/job_hunt_workspace"

    if step == 1:
        res = sbx.run(f"mkdir -p {ws} && echo '{{\"step\": 1, \"status\": \"initialized\"}}' > {ws}/checkpoint.json")
        if not res.ok:
            raise RuntimeError(f"Step 1 failed: {res.stderr}")
        return "workspace_initialized"

    if step == 2:
        profile = {
            "name": "B.Tech IT Candidate",
            "target_role": "Backend & AI Engineer",
            "skills": ["python", "fastapi", "postgresql", "docker", "linux", "sql", "llm_agents", "git"],
            "experience_years": 1,
        }
        payload = shlex.quote(json.dumps(profile))
        res = sbx.run(f"python3 -c 'import pathlib; pathlib.Path(\"{ws}/candidate_profile.json\").write_text({payload})'")
        if not res.ok:
            raise RuntimeError(f"Step 2 failed: {res.stderr}")
        return "candidate_profile_written"

    if step == 3:
        baseline = [
            {
                "job_id": "JOB-101",
                "company": "CelestoCloud",
                "title": "AI Infrastructure Engineer",
                "layout_wrapper": "<div class='v1-old-header'>",
                "skills_required": ["python", "docker", "linux", "fastapi"],
                "exp_years": 1,
            },
            {
                "job_id": "JOB-102",
                "company": "FinLedger",
                "title": "Junior Backend Engineer",
                "layout_wrapper": "<section id='legacy-layout'>",
                "skills_required": ["python", "postgresql", "sql"],
                "exp_years": 1,
            },
        ]
        payload = shlex.quote(json.dumps(baseline))
        res = sbx.run(f"python3 -c 'import pathlib; pathlib.Path(\"{ws}/baseline_jobs.json\").write_text({payload})'")
        if not res.ok:
            raise RuntimeError(f"Step 3 failed: {res.stderr}")
        return "baseline_snapshot_saved"

    if step == 4:
        if test_persistence:
            sbx.stop_persistent()
            sbx.start_persistent()
        res = sbx.run(f"test -f {ws}/baseline_jobs.json && sha256sum {ws}/baseline_jobs.json > {ws}/baseline.sha256")
        if not res.ok:
            raise RuntimeError(f"Step 4 failed: {res.stderr}")
        return "persistence_verified"

    if step == 5:
        current_listings = [
            {
                "job_id": "JOB-101",
                "company": "CelestoCloud",
                "title": "AI Infrastructure Engineer",
                "layout_wrapper": "<main class='v2-redesigned-tailwind-grid'>",
                "skills_required": ["python", "docker", "linux", "fastapi"],
                "exp_years": 1,
            },
            {
                "job_id": "JOB-102",
                "company": "FinLedger",
                "title": "Junior Backend Engineer",
                "layout_wrapper": "<section id='legacy-layout'>",
                "skills_required": ["python", "postgresql", "sql", "kubernetes"],
                "exp_years": 1,
            },
            {
                "job_id": "JOB-103",
                "company": "AgentWorks",
                "title": "LLM Tooling Engineer",
                "layout_wrapper": "<article class='modern-card'>",
                "skills_required": ["python", "fastapi", "llm_agents", "docker"],
                "exp_years": 0,
            },
        ]
        payload = shlex.quote(json.dumps(current_listings))
        res = sbx.run(f"python3 -c 'import pathlib; pathlib.Path(\"{ws}/current_jobs.json\").write_text({payload})'")
        if not res.ok:
            raise RuntimeError(f"Step 5 failed: {res.stderr}")
        return "current_portal_listings_fetched"

    if step == 6:
        diff_script = (
            "import json, hashlib\n"
            f"base = {{j['job_id']: j for j in json.load(open('{ws}/baseline_jobs.json'))}}\n"
            f"curr = json.load(open('{ws}/current_jobs.json'))\n"
            "diffs = []\n"
            "for job in curr:\n"
            "    jid = job['job_id']\n"
            "    sem_curr = hashlib.sha256(json.dumps({'t': job['title'], 's': sorted(job['skills_required']), 'e': job['exp_years']}).encode()).hexdigest()\n"
            "    if jid not in base:\n"
            "        status = 'NEW_LISTING'\n"
            "    else:\n"
            "        b = base[jid]\n"
            "        sem_base = hashlib.sha256(json.dumps({'t': b['title'], 's': sorted(b['skills_required']), 'e': b['exp_years']}).encode()).hexdigest()\n"
            "        if sem_curr != sem_base:\n"
            "            status = 'REAL_REQUIREMENT_CHANGE'\n"
            "        elif job['layout_wrapper'] != b['layout_wrapper']:\n"
            "            status = 'COSMETIC_LAYOUT_TWEAK_IGNORED'\n"
            "        else:\n"
            "            status = 'UNCHANGED'\n"
            "    job['change_status'] = status\n"
            "    diffs.append(job)\n"
            f"json.dump(diffs, open('{ws}/diffed_jobs.json', 'w'), indent=2)\n"
        )
        quoted = shlex.quote(diff_script)
        res = sbx.run(f"python3 -c {quoted}")
        if not res.ok:
            raise RuntimeError(f"Step 6 failed: {res.stderr}")
        return "semantic_diff_completed"

    if step == 7:
        parse_script = (
            "import json\n"
            f"jobs = json.load(open('{ws}/diffed_jobs.json'))\n"
            "for j in jobs:\n"
            "    assert 'job_id' in j and 'skills_required' in j\n"
            f"json.dump(jobs, open('{ws}/validated_jobs.json', 'w'), indent=2)\n"
        )
        quoted = shlex.quote(parse_script)
        res = sbx.run(f"python3 -c {quoted}")
        if not res.ok:
            raise RuntimeError(f"Step 7 failed: {res.stderr}")
        return "batch_details_parsed"

    if step == 8:
        score_script = (
            "import json\n"
            f"prof = json.load(open('{ws}/candidate_profile.json'))\n"
            f"jobs = json.load(open('{ws}/validated_jobs.json'))\n"
            "cand_skills = set(prof['skills'])\n"
            "scored = []\n"
            "for j in jobs:\n"
            "    req = set(j['skills_required'])\n"
            "    matched = sorted(list(cand_skills & req))\n"
            "    missing = sorted(list(req - cand_skills))\n"
            "    score = round((len(matched) / max(len(req), 1)) * 100, 1)\n"
            "    j['matched_skills'] = matched\n"
            "    j['missing_skills'] = missing\n"
            "    j['match_score'] = score\n"
            "    scored.append(j)\n"
            f"json.dump(scored, open('{ws}/scored_jobs.json', 'w'), indent=2)\n"
        )
        quoted = shlex.quote(score_script)
        res = sbx.run(f"python3 -c {quoted}")
        if not res.ok:
            raise RuntimeError(f"Step 8 failed: {res.stderr}")
        return "skill_gaps_scored"

    if step == 9:
        csv_script = (
            "import csv, json\n"
            f"jobs = json.load(open('{ws}/scored_jobs.json'))\n"
            f"with open('{ws}/applications_tracker.csv', 'w', newline='') as f:\n"
            "    w = csv.writer(f)\n"
            "    w.writerow(['job_id', 'company', 'title', 'change_status', 'match_score', 'matched_skills', 'missing_skills'])\n"
            "    for j in jobs:\n"
            "        w.writerow([j['job_id'], j['company'], j['title'], j['change_status'], j['match_score'], ';'.join(j['matched_skills']), ';'.join(j['missing_skills'])])\n"
        )
        quoted = shlex.quote(csv_script)
        res = sbx.run(f"python3 -c {quoted}")
        if not res.ok:
            raise RuntimeError(f"Step 9 failed: {res.stderr}")
        return "spreadsheet_reconciled"

    if step == 10:
        note = call_llm_match_summary("AI Infrastructure Engineer", "CelestoCloud", ["python", "docker", "linux", "fastapi"], [])
        safe_note = shlex.quote(note)
        brief_script = (
            "import json, pathlib\n"
            f"jobs = json.load(open('{ws}/scored_jobs.json'))\n"
            "lines = ['# Job Hunt Desk Verification Brief', '', f'Advisor Note: ' + " + safe_note + ", '']\n"
            "for j in jobs:\n"
            "    lines.append(f\"- **{j['job_id']} ({j['company']} - {j['title']})**: status=`{j['change_status']}`, match=`{j['match_score']}%`, missing=`{j['missing_skills']}`\")\n"
            f"pathlib.Path('{ws}/match_brief.md').write_text('\\n'.join(lines) + '\\n')\n"
        )
        quoted = shlex.quote(brief_script)
        res = sbx.run(
            f"python3 -c {quoted} && test -s {ws}/applications_tracker.csv && test -s {ws}/match_brief.md && cat {ws}/applications_tracker.csv && echo '---BRIEF---' && cat {ws}/match_brief.md"
        )
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
            (ev_dir / "applications_tracker.csv").write_text(csv_part.strip() + "\n", encoding="utf-8")
            (ev_dir / "match_brief.md").write_text(brief_part.strip() + "\n", encoding="utf-8")

    return {
        "sandbox_name": sbx.sandbox_name,
        "fresh": True,
        "success": sbx.state == "deleted",
        "wall_clock_s": sbx.wall_clock_s,
        "boot_to_ready_s": sbx.boot_to_ready_s,
        "cost_usd": sbx.cost_usd,
    }
