CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR(128) PRIMARY KEY,
    sandbox_name VARCHAR(128) NOT NULL UNIQUE,
    problem_id VARCHAR(128) NOT NULL,
    state VARCHAR(32) NOT NULL CHECK (state IN ('created', 'ready', 'running', 'succeeded', 'failed', 'deleted')),
    execution_target VARCHAR(64) NOT NULL CHECK (execution_target = 'celesto_sandbox'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO runs (run_id, sandbox_name, problem_id, state, execution_target)
VALUES ('run-seed-0001', 'sbx-seeddemo1', 'job-hunt-desk', 'deleted', 'celesto_sandbox')
ON CONFLICT (sandbox_name) DO NOTHING;
