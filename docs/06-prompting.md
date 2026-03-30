# 06. Prompting

## 목적

브로커가 inbox에 메시지를 전달할 때, 역할별 context를 포함한 prompt를 생성한다.
AI CLI가 메시지를 올바르게 해석하고 적절한 형식으로 응답하도록 안내한다.

## 참조 초안

- `.draft/cli/cmux_agent/prompting.py` — prompt builder 참고
- `.draft/cli/docs/2026-03-28-controller-message-prompting.md` — 전달 시점 prompt 주입

## 핵심 원칙

- **프로토콜 사전 주입**: start 시 각 AI CLI에 역할/형식/경로를 프로토콜 파일로 안내
- **메시지 자동 주입**: broker가 inbox 전달 후 AI CLI 터미널에 send_text로 직접 주입
- AI CLI가 어떤 provider인지 상관없이 동일한 형식 사용
- 역할 지시는 짧고 명확하게 — AI CLI의 system prompt과 충돌하지 않도록

## 역할별 지시

| 역할 | 핵심 규칙 |
| --- | --- |
| orchestrator | 분석, 계획, 작업 분해. **직접 실행 금지**. dispatch artifact로 worker에 위임. |
| worker | 할당된 작업 수행. 완료 시 result artifact 생성. |

## Prompt 유형

### 1. Dispatch Delivery (→ Worker inbox)

orchestrator가 worker에 작업을 위임할 때, worker의 inbox에 전달되는 메시지.

```json
{
  "message_id": "msg-abc-123",
  "from": "orchestrator",
  "type": "dispatch",
  "task": "로그인 API 엔드포인트를 구현하라.",
  "instructions": "작업 완료 후 .cmux/outbox/ 에 result artifact를 생성하세요.",
  "artifact_format": {
    "type": "result",
    "sender": "worker-1",
    "recipient": "orchestrator",
    "message": "작업 결과 요약"
  },
  "created_at": "2026-03-29T10:00:00Z"
}
```

### 2. Result Delivery (→ Orchestrator inbox)

worker가 결과를 반환할 때, orchestrator의 inbox에 전달되는 메시지.

```json
{
  "message_id": "msg-def-456",
  "from": "worker-1",
  "type": "result",
  "result": "로그인 API 구현 완료. POST /api/auth/login 추가.",
  "instructions": "추가 작업이 필요하면 dispatch artifact를 생성하세요.",
  "artifact_format": {
    "type": "dispatch",
    "sender": "orchestrator",
    "recipient": "worker-N",
    "message": "작업 지시"
  },
  "created_at": "2026-03-29T10:01:00Z"
}
```

### 3. Initial Prompt (run 시작 시)

run 시작 시 각 agent에 역할을 안내하는 초기 메시지.

**Orchestrator 초기 메시지**:
- 역할 설명 (분석, 계획, 작업 분해)
- 사용 가능한 worker 목록
- dispatch artifact 형식 안내
- outbox 경로 안내

**Worker 초기 메시지**:
- 역할 설명 (작업 수행)
- inbox 경로 안내
- result artifact 형식 안내
- outbox 경로 안내

## Prompt 유형 추가: 주입 프롬프트 (Injection Prompt)

broker가 inbox 전달 후 AI CLI 터미널에 `cmux send`로 주입하는 프롬프트.

### Dispatch 주입 (→ worker 터미널)

```
[cmux-agent] orchestrator로부터 작업이 도착했습니다.

작업: {message}

위 작업을 수행하세요.
완료 후 .cmux/outbox/ 에 result artifact를 생성하세요.
```

### Result 주입 (→ orchestrator 터미널)

```
[cmux-agent] {worker-name}의 작업 결과입니다.

결과: {message}

추가 작업이 필요하면 .cmux/outbox/ 에 dispatch artifact를 생성하세요.
모든 작업이 완료되었으면 최종 결과를 보고하세요.
```

## Prompt Builder

```python
class PromptBuilder:
    def build_delivery(sender, recipient, msg_type, payload) -> dict:
        """inbox에 저장할 JSON delivery 메시지를 생성한다."""

    def build_injection_prompt(sender, recipient, msg_type, payload) -> str:
        """AI CLI 터미널에 send_text로 주입할 자연어 프롬프트를 생성한다."""

    def build_initial_orchestrator(workers: list[Agent]) -> dict:
        """orchestrator 초기 안내 메시지를 생성한다."""

    def build_initial_worker(name: str) -> dict:
        """worker 초기 안내 메시지를 생성한다."""

    def write_protocol_files(base_dir, workers) -> None:
        """AI CLI가 읽을 프로토콜 파일(ORCHESTRATOR.md, WORKER-N.md)을 생성한다."""
```

## 작업 항목

1. dispatch delivery 메시지 생성
2. result delivery 메시지 생성
3. injection prompt 생성 (dispatch → worker, result → orchestrator)
4. initial orchestrator 메시지 생성
5. initial worker 메시지 생성
6. 프로토콜 파일 생성 (ORCHESTRATOR.md, WORKER.md)
7. artifact 형식 템플릿
8. 단위 테스트

## 설계 참고

- injection prompt는 자연어 — AI CLI가 사용자 입력으로 인식하여 즉시 반응
- inbox 파일은 JSON — 구조화된 기록용
- 두 가지(주입 프롬프트 + inbox 파일)가 동시에 전달됨
- AI CLI가 입력 대기 상태여야 send_text 주입이 유효
- worker 목록은 orchestrator에만 제공 — worker는 다른 worker를 알 필요 없음
