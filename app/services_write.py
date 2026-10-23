from app.db import get_db_connection
from app.models_write import RunCreateRequest


def create_or_update_run(payload: RunCreateRequest) -> dict:
    query = """
        INSERT INTO runs (run_id, sandbox_name, problem_id, state, execution_target)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (run_id) DO UPDATE
        SET sandbox_name = EXCLUDED.sandbox_name,
            problem_id = EXCLUDED.problem_id,
            state = EXCLUDED.state,
            execution_target = EXCLUDED.execution_target
        RETURNING run_id, sandbox_name, problem_id, state, execution_target, created_at;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    payload.run_id,
                    payload.sandbox_name,
                    payload.problem_id,
                    payload.state,
                    payload.execution_target,
                ),
            )
            row = cur.fetchone()
        conn.commit()
    if row and row.get("created_at") is not None:
        row["created_at"] = row["created_at"].isoformat()
    return row
