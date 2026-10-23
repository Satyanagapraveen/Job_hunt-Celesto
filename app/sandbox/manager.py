from dataclasses import dataclass
import secrets
import signal
import string
import time
from typing import Callable, Optional

from celesto import Computer

from app.config import CELESTO_PROVIDER
from app.models_write import RunCreateRequest
from app.sandbox.safety import (
    CommandBlockedError,
    append_command_audit_log,
    evaluate_command_safety,
    validate_sandbox_name,
)
from app.services_write import create_or_update_run

MICRO_HOURLY_USD = 0.015


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def generate_sandbox_name(prefix: str = "job") -> str:
    clean_prefix = "".join(c for c in prefix.lower() if c in string.ascii_lowercase + string.digits)[:4]
    alphabet = string.ascii_lowercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(8))
    name = f"sbx-{clean_prefix}{suffix}"
    validate_sandbox_name(name)
    return name


class CelestoSandboxSession:
    def __init__(
        self,
        sandbox_name: Optional[str] = None,
        run_id: Optional[str] = None,
        problem_id: str = "job-hunt-desk",
        provider: str = CELESTO_PROVIDER,
        ledger_callback: Optional[Callable[[RunCreateRequest], dict]] = None,
    ):
        self.sandbox_name = sandbox_name or generate_sandbox_name("job")
        validate_sandbox_name(self.sandbox_name)
        self.run_id = run_id or f"run-{self.sandbox_name}"
        self.problem_id = problem_id
        self.provider = provider
        self.ledger_callback = ledger_callback or self._default_ledger_write

        self._computer: Optional[Computer] = None
        self.computer_id: Optional[str] = None
        self.state: str = "init"
        self.created_ts: float = 0.0
        self.ready_ts: float = 0.0
        self.ended_ts: float = 0.0
        self.boot_to_ready_s: float = 0.0
        self.wall_clock_s: float = 0.0
        self.cost_usd: float = 0.0
        self.cleaned_up: bool = False
        self._prev_sigint = None
        self._prev_sigterm = None

    def _default_ledger_write(self, req: RunCreateRequest) -> dict:
        try:
            return create_or_update_run(req)
        except Exception:
            return req.model_dump()

    def _record_state(self, new_state: str) -> None:
        self.state = new_state
        req = RunCreateRequest(
            run_id=self.run_id,
            sandbox_name=self.sandbox_name,
            problem_id=self.problem_id,
            state=new_state,
            execution_target="celesto_sandbox",
        )
        self.ledger_callback(req)

    def _install_signal_handlers(self) -> None:
        def _handle_signal(signum, frame):
            self.cleanup(interrupted=True)
            raise KeyboardInterrupt(f"Interrupted by signal {signum}; sandbox {self.sandbox_name} deleted.")

        try:
            self._prev_sigint = signal.getsignal(signal.SIGINT)
            self._prev_sigterm = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGINT, _handle_signal)
            signal.signal(signal.SIGTERM, _handle_signal)
        except ValueError:
            pass

    def _restore_signal_handlers(self) -> None:
        try:
            if self._prev_sigint is not None:
                signal.signal(signal.SIGINT, self._prev_sigint)
            if self._prev_sigterm is not None:
                signal.signal(signal.SIGTERM, self._prev_sigterm)
        except ValueError:
            pass

    def start(self) -> "CelestoSandboxSession":
        self._install_signal_handlers()
        self.created_ts = time.perf_counter()
        self._computer = Computer(provider=self.provider)
        self._computer.__enter__()
        self.computer_id = getattr(self._computer, "computer_id", None) or getattr(self._computer, "id", None)
        self._record_state("created")

        probe = self.run("echo ready", is_boot_probe=True)
        if not probe.ok:
            raise RuntimeError(f"Sandbox boot probe failed: {probe.stderr}")

        self.ready_ts = time.perf_counter()
        self.boot_to_ready_s = round(self.ready_ts - self.created_ts, 4)
        self._record_state("ready")
        return self

    def run(self, command: str, is_boot_probe: bool = False) -> CommandResult:
        if not is_boot_probe and self.state == "ready":
            self._record_state("running")

        decision, reason, category = evaluate_command_safety(command)
        append_command_audit_log(
            sandbox_name=self.sandbox_name,
            command=command,
            decision=decision,
        )

        if decision == "block":
            raise CommandBlockedError(command=command, reason=reason, category=category)

        if self._computer is None:
            raise RuntimeError("Sandbox computer is not started")

        raw = self._computer.run(command)
        return CommandResult(
            exit_code=int(getattr(raw, "exit_code", 0)),
            stdout=str(getattr(raw, "stdout", "")),
            stderr=str(getattr(raw, "stderr", "")),
        )

    def stop_persistent(self) -> None:
        if self._computer is not None and hasattr(self._computer, "stop"):
            self._computer.stop()

    def start_persistent(self) -> None:
        if self._computer is not None and hasattr(self._computer, "start"):
            self._computer.start()

    def mark_succeeded(self) -> None:
        self._record_state("succeeded")

    def mark_failed(self) -> None:
        self._record_state("failed")

    def cleanup(self, interrupted: bool = False) -> None:
        if self.cleaned_up:
            return
        try:
            if self._computer is not None:
                self._computer.__exit__(None, None, None)
                self._computer = None
        finally:
            self.ended_ts = time.perf_counter()
            if self.created_ts > 0:
                self.wall_clock_s = round(self.ended_ts - self.created_ts, 4)
                hours = self.wall_clock_s / 3600.0
                self.cost_usd = round(max(hours * MICRO_HOURLY_USD, 0.0001), 6)
            self._record_state("deleted")
            self.cleaned_up = True
            self._restore_signal_handlers()

    def __enter__(self) -> "CelestoSandboxSession":
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        try:
            if exc_type is not None and self.state not in ("succeeded", "failed", "deleted"):
                self.mark_failed()
            elif exc_type is None and self.state == "running":
                self.mark_succeeded()
        finally:
            self.cleanup()
        return False
