# ReplyPilot LLMOps 진단 시연 시나리오

## 목표

5~7분 안에 “관찰 가능성 → 실패 원인 진단 → 품질 게이트”를 보여준다. 실제 Gmail 연결 전에는 mock 데이터로 반복 가능하게 시연하고, live 전환 후 동일한 run 구조를 LangSmith에서 확인한다.

## 사전 준비

```bash
cd backend
uv sync
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY='로컬 secret에서 주입'
export LANGSMITH_PROJECT=replypilot-demo
export LANGSMITH_HIDE_INPUTS=true
export LANGSMITH_HIDE_OUTPUTS=true
uv run replypilot-api
```

별도 터미널에서 `X-ReplyPilot-Key`를 사용해 `/api/runs/scan`을 호출한다. 키와 Gmail OAuth 토큰은 화면·로그·녹화에 표시하지 않는다.

## 시연 흐름

1. **정상 run 추적** — LangSmith에서 `replypilot-email-workflow` trace를 열고 `triage → context → draft → review` 순서, 각 단계 latency, 토큰 사용량을 확인한다. Hosted trace의 이메일·초안 원문은 숨김 상태를 유지한다.
2. **사람 승인 중단** — API 응답의 `awaiting_approval`과 LangGraph checkpoint를 보여준다. 이 시점의 Gmail draft 수는 0임을 확인한다.
3. **승인 후 재개** — `approve` 결정을 보내 동일한 `thread_id`가 `draft_saved`로 끝나고 Gmail에는 초안만 만들어짐을 확인한다.
4. **진단 사례** — 회신 불필요 뉴스레터가 `no_reply_needed`로 빠지는 trace와, 낮은 review 점수가 최대 1회 재작성되는 분기를 비교한다.
5. **평가 실행** — `uv run replypilot-eval`로 로컬 결과를 출력하고 LangSmith experiment의 `triage_accuracy`를 확인한다.

## 통과 기준

| 지표 | MVP 기준 |
|---|---:|
| 회신 필요 분류 정확도 | ≥ 90% (대표 데이터셋 확장 후) |
| 평균 초안 적합성 | ≥ 4.0 / 5.0 |
| 승인 전 Gmail 쓰기 | 0건 |
| 자동 전송 | 0건 |
| trace 누락률 | < 1% |

현재 저장소의 smoke 평가 3건은 회귀 방지용일 뿐 통계적 품질 증거가 아니다. 실제 합격 판정 전에는 개인정보를 비식별화한 최소 100건 이상의 대표 데이터셋과 사람 평가자 간 합의 기준을 추가한다.

## 진단 체크리스트

- 분류 오류: 입력 분포, sender 유형, prompt/version, confidence를 비교
- 초안 오류: 원문 근거 누락, 환각된 약속, 어조, 길이를 review issue로 분해
- 지연 증가: 노드별 latency와 Gmail API latency를 분리
- 비용 증가: 모델·노드별 토큰 수와 재작성률을 비교
- 운영 오류: OAuth refresh, rate limit, checkpoint 재개, 중복 승인 여부를 audit event와 대조
