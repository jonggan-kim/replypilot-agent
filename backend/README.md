# ReplyPilot backend

LangGraph 기반의 이메일 분류·회신 초안 에이전트입니다. 기본 실행은 자격증명과 외부 호출이 전혀 없는 `mock` 모드입니다. 실제 모드에서도 사람의 승인 전에는 Gmail 변경이 없고, 승인 후에도 **초안만 생성**합니다. 이메일 전송 API는 구현하거나 노출하지 않습니다.

## 구성

```text
Hermes Agent ──stdio MCP──> ReplyPilot
                              ├─ Supervisor (LangGraph)
                              ├─ Triage / Context / Draft / Review agents
                              ├─ Human interrupt + durable checkpoint
                              ├─ Gmail adapter (read + create draft only)
                              └─ LangSmith traces / evaluations
```

상태 전이는 다음과 같습니다.

```text
scan → triage ──no reply──> complete
              └─reply──> context → draft → review(≥4/5)
                                           ↓
                                  human approval interrupt
                                  ├─ reject → complete
                                  └─ approve/revise → Gmail draft
```

## 1. 로컬 mock 실행

Python 3.12 또는 3.13과 `uv`를 사용합니다.

```bash
uv sync
cp .env.example .env
uv run pytest
uv run replypilot-eval
uv run replypilot-api
```

API는 `127.0.0.1:8000`에만 바인딩됩니다. `.env`의 `REPLYPILOT_CONTROL_TOKEN`을 충분히 긴 임의 값으로 변경한 뒤 요청에 `X-ReplyPilot-Key` 헤더로 전달합니다.

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/api/runs/scan \
  -H 'Content-Type: application/json' \
  -H 'X-ReplyPilot-Key: replace-with-a-long-random-value' \
  -d '{"max_results":3}'
```

## 2. Hermes Gateway 연결

`~/.hermes/config.yaml`에 아래 서버 하나만 추가합니다. `/ABSOLUTE/PATH/backend`은 이 디렉터리의 절대 경로로 바꿉니다.

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

연결 확인:

```bash
hermes mcp test replypilot
```

`trust: untrusted`는 쓰기 가능 도구에 Hermes 승인 UI를 추가합니다. `review_draft`는 승인 시 Gmail 초안을 만들 수 있으므로 병렬 호출을 끕니다. `sampling`도 끄고, LLM 호출은 ReplyPilot과 LangSmith에서 일관되게 추적합니다.

## 3. Gmail OAuth 설정

1. Google Cloud Console에서 Gmail API를 활성화합니다.
2. OAuth 동의 화면을 구성하고 **Desktop app** 유형의 OAuth 클라이언트를 만듭니다.
3. 다운로드한 client secret JSON을 저장소 밖에 보관합니다.
4. `.env`에 절대 경로를 설정하고 OAuth를 한 번 수행합니다.

```bash
REPLYPILOT_GOOGLE_CLIENT_SECRET_PATH=/secure/path/client_secret.json uv run replypilot-google-auth
```

Refresh token은 평문 파일이 아니라 운영체제 keyring에 저장됩니다. 앱은 다음 두 범위만 요청합니다.

- `gmail.readonly`: 후보·스레드 읽기
- `gmail.compose`: 초안 생성

Google의 `gmail.compose` 범위 자체에는 전송 능력도 포함되지만, 이 코드베이스에는 `send` 메서드·API·MCP 도구가 없습니다. 운영 환경에서는 Google OAuth 앱 검증 및 제한 범위 보안 평가 요건도 별도로 확인해야 합니다.

## 4. OpenAI + LangSmith live 모드

키를 코드, Git, Hermes YAML 또는 채팅에 넣지 말고 로컬 secret 환경에만 설정합니다.

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

`uv run replypilot-eval`은 항상 로컬 품질 게이트를 출력합니다. `LANGSMITH_API_KEY`가 있으면 `replypilot-smoke-eval-v1` 데이터셋을 만들거나 재사용해 LangSmith 실험도 실행합니다. MVP 합격 기준은 회신 필요 분류 정확도와 평균 초안 검토 점수 `≥ 4/5`입니다.

## 보안 기본값

- 자동 전송 없음; Gmail 초안만 생성
- 사람 승인 전 외부 쓰기 없음
- API 제어 토큰 비교, localhost 바인딩
- OAuth refresh token은 OS keyring 저장
- `.env`, client secret, SQLite 데이터베이스는 Git 제외
- Hermes MCP 도구 allowlist 및 `untrusted` 승인 정책
- raw 이메일 본문·토큰을 애플리케이션 로그에 기록하지 않음
- hosted LangSmith trace의 입력·출력은 기본 숨김; 내용 기반 진단은 비식별 평가 데이터만 사용
- checkpoint에는 워크플로 재개용 원문이 포함되므로 운영 DB는 암호화 디스크·접근통제·보존기간을 적용
