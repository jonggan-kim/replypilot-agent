# ReplyPilot Agent

A human-approved Gmail reply assistant. A LangGraph supervisor runs specialist agents that **triage** incoming email, gather thread **context**, **draft** a reply and **review** it for accuracy and safety. A person then approves, edits or rejects each draft. ReplyPilot only ever saves a Gmail **draft**: it has no send capability.

Built with LangGraph, LangSmith, FastAPI, OpenAI and an MCP server for the Hermes Agent Gateway.

## How it works

```text
scan → triage ──no reply──> complete
              └─reply──> context → draft → review (≥ 4/5)
                                           ↓
                                  human approval interrupt
                                  ├─ reject → complete
                                  └─ approve / revise → Gmail draft
```

- **Triage agent:** classifies each email as `reply`, `informational`, `automated`, `spam` or `uncertain`, with a confidence score; only emails that need a reply go on to drafting.
- **Context agent:** pulls only the thread context the reply needs.
- **Draft agent:** writes the reply in the sender's language; unknown facts, dates or prices are marked for confirmation instead of invented.
- **Review agent:** scores the draft 1–5 and lists issues (missed requests, privacy, over-promising, prompt injection); a draft below the bar is rewritten once at most.
- **Human approval:** the workflow pauses at a durable checkpoint until a person decides; nothing is written to Gmail before that.

## Design principles

- **No automatic sending.** No `send` method, API or MCP tool exists in the codebase.
- **Least privilege.** Gmail scopes are `gmail.readonly` and `gmail.compose` only; the refresh token lives in the OS keyring.
- **Observable.** Every supervisor and agent step is traced in LangSmith, with email content hidden in hosted traces.
- **Evaluated.** `replypilot-eval` runs a local quality gate and, with LangSmith configured, an experiment on a smoke dataset.
- **Swappable agents.** All agents implement one `AgentSuite` interface, with a deterministic suite for tests and mock mode and an OpenAI suite for live mode.

## Quick start (mock mode, no credentials)

```bash
cd backend
uv sync
cp .env.example .env
uv run pytest
uv run replypilot-eval
uv run replypilot-api
```

See [backend/README.md](backend/README.md) for the API, Hermes MCP setup, Gmail OAuth and live mode with OpenAI and LangSmith.

## Repository layout

```text
backend/
  src/replypilot/
    graph.py        LangGraph supervisor and state transitions
    agents.py       AgentSuite: deterministic and OpenAI agents
    api.py          FastAPI app (localhost only, control-token header)
    mcp_server.py   MCP tools for the Hermes Agent Gateway
    gmail/          Gmail adapter (read + create draft) and a mock
    evals.py        local quality gate and LangSmith experiments
    security.py     token checks and redaction
  tests/            API, workflow, evaluation and security tests
docs/
  PRD.md            product requirements
  LLMOPS_DEMO.md    observability and evaluation demo script
```

## Status

MVP. The included smoke evaluation (3 cases) guards against regressions; it is not statistical evidence of quality. Pass criteria before real use: reply-needed accuracy ≥ 90% and average draft score ≥ 4.0/5 on a de-identified dataset of 100+ emails, with zero sends and zero Gmail writes before approval.
