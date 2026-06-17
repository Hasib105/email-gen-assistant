-- Production schema for case data, jobs, and draft approval workflows.

CREATE TABLE IF NOT EXISTS cases (
    case_id        text PRIMARY KEY,
    issue_type     text NOT NULL DEFAULT 'general',
    customer_tier  text NOT NULL DEFAULT '',
    payload        jsonb NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    updated_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cases_issue_type ON cases(issue_type);
CREATE INDEX IF NOT EXISTS idx_cases_customer_tier ON cases(customer_tier);

CREATE TABLE IF NOT EXISTS background_jobs (
    job_id         text PRIMARY KEY,
    job_type       text NOT NULL,
    status         text NOT NULL DEFAULT 'queued',
    case_id        text NOT NULL,
    payload        jsonb NOT NULL,
    attempts       integer NOT NULL DEFAULT 0,
    max_attempts   integer NOT NULL DEFAULT 3,
    error          text NOT NULL DEFAULT '',
    created_at     timestamptz NOT NULL,
    updated_at     timestamptz NOT NULL,
    started_at     timestamptz,
    finished_at    timestamptz
);

CREATE INDEX IF NOT EXISTS idx_background_jobs_case_id
    ON background_jobs(case_id);

CREATE INDEX IF NOT EXISTS idx_background_jobs_status
    ON background_jobs(status);

CREATE TABLE IF NOT EXISTS draft_approvals (
    case_id        text PRIMARY KEY,
    draft          jsonb NOT NULL,
    status         text NOT NULL DEFAULT 'pending',
    created_by     text NOT NULL,
    created_at     timestamptz NOT NULL,
    updated_at     timestamptz NOT NULL,
    approved_by    text NOT NULL DEFAULT '',
    approved_at    timestamptz,
    review_notes   text NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS draft_audit_events (
    id             bigserial PRIMARY KEY,
    case_id        text NOT NULL REFERENCES draft_approvals(case_id),
    event_type     text NOT NULL,
    user_id        text NOT NULL,
    created_at     timestamptz NOT NULL,
    note           text NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_draft_audit_case_id
    ON draft_audit_events(case_id);
