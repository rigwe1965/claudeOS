-- Phase 10.3: LLM-as-Judge eval columns on agent_runs
ALTER TABLE agent_runs ADD COLUMN eval_score REAL;
ALTER TABLE agent_runs ADD COLUMN eval_reasoning TEXT;
ALTER TABLE agent_runs ADD COLUMN eval_dimensions TEXT;  -- JSON: {task_completion, factual_grounding, conciseness, safety}
ALTER TABLE agent_runs ADD COLUMN eval_at TEXT;

CREATE INDEX IF NOT EXISTS idx_agent_runs_eval_score
    ON agent_runs(eval_score) WHERE eval_score IS NOT NULL;
