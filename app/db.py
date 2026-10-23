from contextlib import contextmanager
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from app.config import DATABASE_URL

SEED_SQL_PATH = Path(__file__).resolve().parent.parent / "seeds" / "01_runs.sql"


@contextmanager
def get_db_connection():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    if not SEED_SQL_PATH.exists():
        return
    sql_script = SEED_SQL_PATH.read_text(encoding="utf-8")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_script)
        conn.commit()


def check_db_health() -> bool:
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                row = cur.fetchone()
                return row is not None
    except Exception:
        return False
