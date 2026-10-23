from typing import Optional
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class RunReadResponse(BaseModel):
    run_id: str
    sandbox_name: str
    problem_id: str
    state: str
    execution_target: str
    created_at: Optional[str] = None
