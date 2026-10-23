from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Tuple

from app.config import COMMAND_LOG_PATH

SAND_NAME_PATTERN = re.compile(r"^sbx-[a-z0-9]{8,}$")

DESTRUCTIVE_PATTERNS = [
    r"rm\s+-rf\s+/(?:\s|$|\*)",
    r"rm\s+-rf\s+~",
    r"mkfs\.",
    r"dd\s+if=/dev/zero",
    r":\(\)\{\s*:\|:&\s*\};:",
    r"chmod\s+-R\s+777\s+/",
]

EXFIL_PATTERNS = [
    r"curl\s+.*(?:\$[A-Z_]*KEY|\$[A-Z_]*SECRET|\$[A-Z_]*TOKEN|/etc/passwd|\.env)",
    r"wget\s+.*(?:\$[A-Z_]*KEY|\$[A-Z_]*SECRET|\$[A-Z_]*TOKEN|/etc/passwd|\.env)",
    r"http://evil-recruiter\.example",
    r"https?://attacker\.example",
    r"nc\s+-e\s+/bin/(?:ba)?sh",
]

SUSPICIOUS_PKG_PATTERNS = [
    r"pip\s+install\s+.*(?:evil-pkg|typosquat-requests|malicious-job-parser)",
    r"npm\s+install\s+.*(?:evil-pkg|malicious-scraper)",
    r"curl\s+.*\|\s*(?:ba)?sh",
]


class CommandBlockedError(RuntimeError):
    def __init__(self, command: str, reason: str, category: str):
        super().__init__(f"Blocked command ({category}): {reason}")
        self.command = command
        self.reason = reason
        self.category = category


def validate_sandbox_name(sandbox_name: str) -> None:
    if not SAND_NAME_PATTERN.match(sandbox_name):
        raise ValueError(
            f"Invalid sandbox_name '{sandbox_name}'. Must match ^sbx-[a-z0-9]{{8,}}$"
        )


def evaluate_command_safety(command: str) -> Tuple[str, str, str]:
    if not command or not command.strip():
        return ("block", "Empty command is not permitted", "invalid_command")

    for pattern in EXFIL_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return (
                "block",
                f"Matched prompt-injection exfiltration signature: {pattern}",
                "prompt_injection_exfil",
            )

    for pattern in DESTRUCTIVE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return (
                "block",
                f"Matched destructive command signature: {pattern}",
                "destructive_command",
            )

    for pattern in SUSPICIOUS_PKG_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return (
                "block",
                f"Matched suspicious package signature: {pattern}",
                "suspicious_package",
            )

    return ("allow", "passed_safety_hooks", "none")


def append_command_audit_log(
    sandbox_name: str,
    command: str,
    decision: str,
    log_path: Path = COMMAND_LOG_PATH,
) -> dict:
    validate_sandbox_name(sandbox_name)
    if decision not in ("allow", "block"):
        raise ValueError(f"Invalid decision: {decision}")
    if not command or not command.strip():
        raise ValueError("Command must be a non-empty string")

    log_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "sandbox_name": sandbox_name,
        "command": command,
        "decision": decision,
        "execution_target": "celesto_sandbox",
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    return entry
