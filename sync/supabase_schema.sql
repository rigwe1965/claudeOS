-- ============================================================
-- ClaudeOS — Supabase Schema
-- Run this in: Supabase Dashboard > SQL Editor
-- ============================================================

-- Enable UUID extension (usually already enabled)
-- create extension if not exists "uuid-ossp";

-- ── memory_entries ───────────────────────────────────────────
create table if not exists memory_entries (
    id          text primary key,
    namespace   text not null default 'global',
    category    text not null default 'fact',
    key         text not null,
    value       text not null,
    source      text default 'user',
    agent_id    text,
    session_id  text,
    tags        text default '[]',
    confidence  real default 1.0,
    expires_at  timestamptz,
    notified_at timestamptz,
    created_at  timestamptz default now(),
    updated_at  timestamptz default now()
);
create index if not exists idx_me_namespace on memory_entries(namespace);
create index if not exists idx_me_created on memory_entries(created_at);

-- ── agent_runs ───────────────────────────────────────────────
create table if not exists agent_runs (
    id              text primary key,
    agent_id        text,
    session_id      text,
    namespace       text default 'global',
    input           text not null,
    output          text,
    status          text default 'pending',
    tokens_in       integer default 0,
    tokens_out      integer default 0,
    duration_ms     integer,
    error           text,
    triggered_by    text default 'user',
    workflow_run_id text,
    created_at      timestamptz default now(),
    completed_at    timestamptz,
    eval_score      real,
    eval_reasoning  text,
    eval_dimensions text,
    eval_at         timestamptz
);

-- Migration: add eval columns if upgrading from pre-Phase-10 schema
alter table agent_runs add column if not exists eval_score      real;
alter table agent_runs add column if not exists eval_reasoning  text;
alter table agent_runs add column if not exists eval_dimensions text;
alter table agent_runs add column if not exists eval_at         timestamptz;
create index if not exists idx_ar_namespace on agent_runs(namespace);
create index if not exists idx_ar_created on agent_runs(created_at);

-- ── outputs ──────────────────────────────────────────────────
create table if not exists outputs (
    id              text primary key,
    namespace       text not null default 'global',
    project_id      text,
    agent_run_id    text,
    workflow_run_id text,
    type            text not null default 'report',
    title           text not null,
    content         text not null,
    format          text default 'markdown',
    tags            text default '[]',
    size_bytes      integer default 0,
    summary         text default '',
    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);
create index if not exists idx_out_namespace on outputs(namespace);
create index if not exists idx_out_created on outputs(created_at);

-- ── namespaces ───────────────────────────────────────────────
create table if not exists namespaces (
    id              text primary key,
    slug            text unique not null,
    display_name    text not null,
    description     text default '',
    type            text default 'client',
    color           text default '#407E3C',
    icon            text default '🏢',
    parent_id       text references namespaces(id),
    metadata        text default '{}',
    enabled         integer default 1,
    created_at      timestamptz default now()
);

-- ── projects ─────────────────────────────────────────────────
create table if not exists projects (
    id              text primary key,
    namespace_id    text references namespaces(id),
    name            text not null,
    slug            text not null,
    description     text default '',
    status          text default 'active',
    priority        integer default 2,
    tech_stack      text default '[]',
    path            text default '',
    metadata        text default '{}',
    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

-- ── system_events ────────────────────────────────────────────
create table if not exists system_events (
    id          text primary key,
    event_type  text not null,
    source      text default 'system',
    namespace   text default 'global',
    payload     text default '{}',
    severity    text default 'info',
    created_at  timestamptz default now()
);
create index if not exists idx_se_created on system_events(created_at);

-- ── sync_log (mirror of local) ───────────────────────────────
create table if not exists sync_log (
    id          text primary key,
    table_name  text not null,
    direction   text not null default 'push',
    rows_ok     integer default 0,
    rows_fail   integer default 0,
    duration_ms integer,
    error       text,
    started_at  timestamptz default now(),
    completed_at timestamptz
);

-- ── users (no password_hash, failed_attempts, locked_until — excluded from sync)
create table if not exists users (
    id                   text primary key,
    username             text unique not null,
    email                text,
    role                 text not null default 'viewer',
    namespace            text,
    is_active            integer default 1,
    must_change_password integer default 0,
    last_login_at        timestamptz,
    created_at           timestamptz default now(),
    updated_at           timestamptz default now()
);
create index if not exists idx_users_namespace on users(namespace);

-- ── tickets ──────────────────────────────────────────────────
create table if not exists tickets (
    id          text primary key,
    namespace   text not null default 'global',
    created_by  text not null,
    title       text not null,
    description text not null,
    status      text not null default 'open',
    category    text default 'other',
    priority    integer default 3,
    sla_tier    text,
    sla_due_at  timestamptz,
    assigned_to text,
    resolution  text,
    created_at  timestamptz default now(),
    updated_at  timestamptz default now()
);
create index if not exists idx_tickets_namespace on tickets(namespace);
create index if not exists idx_tickets_status on tickets(status);

-- ── workflows ────────────────────────────────────────────────
create table if not exists workflows (
    id              text primary key,
    name            text unique not null,
    display_name    text not null,
    description     text default '',
    namespace       text default 'global',
    trigger_type    text default 'manual',
    trigger_config  text default '{}',
    steps           text default '[]',
    enabled         integer default 1,
    webhook_enabled integer default 0,
    created_at      timestamptz default now(),
    updated_at      timestamptz default now()
);

-- ── RLS: disable for service key access (adjust per your security model)
alter table memory_entries  disable row level security;
alter table agent_runs      disable row level security;
alter table outputs         disable row level security;
alter table namespaces      disable row level security;
alter table projects        disable row level security;
alter table system_events   disable row level security;
alter table sync_log        disable row level security;
alter table users           disable row level security;
alter table tickets         disable row level security;
alter table workflows       disable row level security;
