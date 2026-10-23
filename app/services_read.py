from app.db import get_db_connection


def list_all_runs() -> list[dict]:
    query = """
        SELECT run_id, sandbox_name, problem_id, state, execution_target, created_at
        FROM runs
        ORDER BY created_at ASC;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    result = []
    for row in rows:
        item = dict(row)
        if item.get("created_at") is not None:
            item["created_at"] = item["created_at"].isoformat()
        result.append(item)
    return result
