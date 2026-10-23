from typing import Literal
from pydantic import BaseModel, Field

AllowedState = Literal[
    "created",
    "ready",
    "running",
    "succeeded",
    "failed",
    "deleted",
]


class RunCreateRequest(BaseModel):
    run_id: str = Field(..., min_length=1, max_length=128)
    sandbox_name: str = Field(..., pattern=r"^sbx-[a-z0-9]{8,}$", max_length=128)
    problem_id: str = Field(..., min_length=1, max_length=128)
    state: AllowedState
    execution_target: Literal["celesto_sandbox"]
