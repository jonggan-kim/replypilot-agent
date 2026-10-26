# ReplyPilot LLMOps Diagnosis Demo Script

## Goal

Show "observability → failure diagnosis → quality gate" in 5–7 minutes. Before connecting real Gmail, demo repeatably with mock data; after switching to live, confirm the same run structure in LangSmith.

## Setup

```bash
cd backend
uv sync
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY='inject from your local secret store'
export LANGSMITH_PROJECT=replypilot-demo
export LANGSMITH_HIDE_INPUTS=true
export LANGSMITH_HIDE_OUTPUTS=true
uv run replypilot-api
```

In a separate terminal, call `/api/runs/scan` with the `X-ReplyPilot-Key` header. Keep keys and Gmail OAuth tokens off the screen, out of logs and out of recordings.

## Demo flow

1. **Trace a normal run** — open the `replypilot-email-workflow` trace in LangSmith and check the `triage → context → draft → review` order, per-step latency and token usage. Raw email and draft text stay hidden in the hosted trace.
2. **Human approval interrupt** — show `awaiting_approval` in the API response and the LangGraph checkpoint. Confirm that the Gmail draft count is 0 at this point.
3. **Resume after approval** — send an `approve` decision and confirm the same `thread_id` ends in `draft_saved`, with only a draft created in Gmail.
4. **Diagnosis cases** — compare a trace where a newsletter that needs no reply exits as `no_reply_needed` with the branch where a low review score triggers at most one rewrite.
5. **Run the evaluation** — print local results with `uv run replypilot-eval` and check `triage_accuracy` in the LangSmith experiment.

## Pass criteria

| Metric | MVP threshold |
|---|---:|
| Reply-needed classification accuracy | ≥ 90% (after expanding to a representative dataset) |
| Average draft suitability | ≥ 4.0 / 5.0 |
| Gmail writes before approval | 0 |
| Automatic sends | 0 |
| Trace miss rate | < 1% |

The three smoke-evaluation cases currently in the repository guard against regressions only; they are not statistical evidence of quality. Before a real pass/fail decision, add a de-identified representative dataset of at least 100 cases and an inter-rater agreement standard for human evaluators.

## Diagnosis checklist

- Classification errors: compare input distribution, sender type, prompt/version and confidence
- Draft errors: break review issues down into missing grounding in the source, hallucinated commitments, tone and length
- Latency increases: separate per-node latency from Gmail API latency
- Cost increases: compare token counts and rewrite rates by model and node
- Operational errors: check OAuth refresh, rate limits, checkpoint resume and duplicate approvals against audit events
