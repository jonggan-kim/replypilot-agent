# ReplyPilot backend

A LangGraph agent that triages email and drafts replies. By default it runs in `mock` mode, with no credentials and no external calls. Even in live mode it changes nothing in Gmail before a person approves, and after approval it **only creates a draft**. No email-sending API is implemented or exposed.

## Architecture

```text
Hermes Agent ──stdio MCP──> ReplyPilot
                              ├─ Supervisor (LangGraph)
                              ├─ Triage / Context / Draft / Review agents
                              ├─ Human interrupt + durable checkpoint
                              ├─ Gmail adapter (read + create draft only)
                              └─ LangSmith traces / evaluations
```

State transitions:

```text
scan → triage ──no reply──> complete
              └─reply──> context → draft → review(≥4/5)
                                           ↓
                                  human approval interrupt
                                  ├─ reject → complete
                                  └─ approve/revise → Gmail draft
```

## 1. Run locally in mock mode

Requires Python 3.12 or 3.13 and `uv`.

```bash
uv sync
cp .env.example .env
uv run pytest
uv run replypilot-eval
uv run replypilot-api
```

The API binds to `127.0.0.1:8000` only. Change `REPLYPILOT_CONTROL_TOKEN` in `.env` to a long random value and send it in the `X-ReplyPilot-Key` header.

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/api/runs/scan \
  -H 'Content-Type: application/json' \
  -H 'X-ReplyPilot-Key: replace-with-a-long-random-value' \
  -d '{"max_results":3}'
```

## 2. Connect the Hermes Gateway

Add this one server to `~/.hermes/config.yaml`. Replace `/ABSOLUTE/PATH/backend` with the absolute path of this directory.

```yaml
mcp_servers:
  replypilot:
    command: "uv"
    args: ["--directory", "/ABSOLUTE/PATH/backend", "run", "replypilot-mcp"]
    enabled: true
    trust: untrusted
    supports_parallel_tool_calls: false
    sampling:
      enabled: false
    tools:
      include:
        - scan_inbox
        - get_run_status
        - list_review_queue
        - review_draft
      resources: false
      prompts: false
```

Check the connection:

```bash
hermes mcp test replypilot
```

`trust: untrusted` adds Hermes's approval UI to tools that can write. `review_draft` can create a Gmail draft when approved, so parallel calls are off. `sampling` is off too, so every LLM call is traced consistently in ReplyPilot and LangSmith.

## 3. Gmail OAuth setup

1. Enable the Gmail API in Google Cloud Console.
2. Configure the OAuth consent screen and create an OAuth client of type **Desktop app**.
3. Keep the downloaded client-secret JSON outside the repository.
4. Set its absolute path in `.env` and run the OAuth flow once.

```bash
REPLYPILOT_GOOGLE_CLIENT_SECRET_PATH=/secure/path/client_secret.json uv run replypilot-google-auth
```

The refresh token is stored in the operating system keyring, not in a plain-text file. The app requests only two scopes:

- `gmail.readonly`: read candidate messages and threads
- `gmail.compose`: create drafts

Google's `gmail.compose` scope itself also allows sending, but this codebase has no `send` method, API or MCP tool. For production, also check Google's OAuth app verification and restricted-scope security assessment requirements.

## 4. Live mode with OpenAI and LangSmith

Keep keys out of code, Git, Hermes YAML and chat; set them only in your local secret environment.

```bash
export OPENAI_API_KEY='...'
export LANGSMITH_API_KEY='...'
export LANGSMITH_TRACING='true'
export LANGSMITH_PROJECT='replypilot-local'
export LANGSMITH_HIDE_INPUTS='true'
export LANGSMITH_HIDE_OUTPUTS='true'
export REPLYPILOT_MODE='live'
export REPLYPILOT_CONTROL_TOKEN='at-least-24-random-characters'
export REPLYPILOT_GOOGLE_CLIENT_SECRET_PATH='/secure/path/client_secret.json'
uv run replypilot-api
```

`uv run replypilot-eval` always prints the local quality gate. With `LANGSMITH_API_KEY` set, it also creates or reuses the `replypilot-smoke-eval-v1` dataset and runs a LangSmith experiment. The MVP pass criteria are reply-needed classification accuracy and an average draft review score of `≥ 4/5`.

## Security defaults

- No automatic sending; Gmail drafts only
- No external writes before human approval
- API control-token check, localhost binding
- OAuth refresh token stored in the OS keyring
- `.env`, client secrets and the SQLite database excluded from Git
- Hermes MCP tool allowlist and `untrusted` approval policy
- Raw email bodies and tokens never written to application logs
- Inputs and outputs hidden in hosted LangSmith traces by default; content-level diagnosis uses de-identified evaluation data only
- Checkpoints hold the original text needed to resume a workflow, so a production database needs an encrypted disk, access control and a retention period
