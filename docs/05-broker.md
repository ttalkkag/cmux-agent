# 05. 메시지 브로커

## 목적

artifact watcher가 감지한 메시지를 파싱하고, 수신자의 inbox에 전달하고,
cmux 알림으로 통보하는 메시지 브로커를 구현한다.

## 참조 초안

- `.draft/cli/plan.md` §10 — 통신 모델
- `.draft/diagram.md` — 메시지 라우팅
- `.draft/dev-automation/01-detail.md` — 메시지 큐 패턴

## 아키텍처 위치

```
AI CLI → outbox/ → [Watcher] → [Broker] → inbox/{recipient}/ → AI CLI
                                   ↓
                              cmux 알림/통보
                                   ↓
                              StateStore 기록
```

## 라우팅 규칙

| Artifact type | 송신자 | 수신자 결정 |
| --- | --- | --- |
| dispatch | orchestrator | artifact 내 `recipient` 필드 |
| result | worker-N | 항상 orchestrator |

## MessageBroker 클래스

```python
class MessageBroker:
    def __init__(self, store: StateStore, cmux: CmuxAdapter):
        ...

    def handle_artifact(self, artifact_path: str, data: dict) -> None:
        """watcher가 감지한 artifact를 처리한다."""

    def route_message(self, run_id: str, sender: str, recipient: str,
                      msg_type: str, payload: dict) -> None:
        """메시지를 수신자에게 라우팅한다."""

    def deliver_to_inbox(self, recipient: str, message: dict) -> str:
        """수신자의 inbox에 메시지 파일을 생성한다."""

    def notify_recipient(self, recipient: str, summary: str) -> None:
        """cmux를 통해 수신자에게 메시지 도착을 통보한다."""

    def get_pending(self, recipient: str) -> list[dict]:
        """미수령 메시지 목록을 반환한다."""
```

## 처리 흐름

### 1. Artifact 수신

watcher → `handle_artifact(path, data)` 호출

### 2. 메시지 생성

- message_id 생성
- Message 레코드를 StateStore에 기록 (PENDING)
- 이벤트 로그 기록 (artifact.detected)

### 3. 라우팅

- recipient 확인 (등록된 agent인지)
- 라우팅 규칙 적용

### 4. Inbox 전달

수신자의 inbox 디렉토리에 메시지 파일 생성:

```
.agent/inbox/{recipient}/{message_id}.json
```

파일 내용:

```json
{
  "message_id": "msg-abc-123",
  "from": "orchestrator",
  "type": "dispatch",
  "message": "로그인 API 엔드포인트를 구현하라.",
  "context": {},
  "created_at": "2026-03-29T10:00:00Z"
}
```

### 5. 통보

- CmuxAdapter.notify()로 macOS 알림
- CmuxAdapter.send_text()로 pane에 간단한 통보 메시지 (선택)
- Message 상태 → DELIVERED
- 이벤트 로그 기록 (message.delivered)

## 에러 처리

| 상황 | 처리 |
| --- | --- |
| recipient가 미등록 agent | 오류 로그, artifact를 failed/로 이동 |
| inbox 디렉토리 없음 | 자동 생성 |
| 파일 쓰기 실패 | 재시도 (최대 3회), 실패 시 FAILED 상태 |
| cmux 통보 실패 | 경고 로그 (메시지 전달은 성공이므로 블로킹하지 않음) |

## Delivery Prompt 연동

메시지를 inbox에 전달할 때, prompting 모듈을 사용하여 역할별 context를 포함할 수 있다.

- dispatch → worker: 작업 지시 + result 블록 형식 안내
- result → orchestrator: 결과 요약 + 다음 행동 안내

이 기능은 06-prompting에서 구현한다.

## 작업 항목

1. MessageBroker 클래스 골격
2. handle_artifact 처리 흐름
3. route_message 라우팅 로직
4. deliver_to_inbox 파일 생성
5. notify_recipient cmux 알림 연동
6. Message 레코드 및 상태 관리
7. 에러 처리 및 재시도
8. 이벤트 로그 연동
9. get_pending 미수령 메시지 조회
10. 단위 테스트

## 설계 참고

- 브로커는 메시지 내용을 해석하지 않음 — 라우팅만 담당
- inbox 파일이 AI CLI에 의해 읽히었는지 확인하는 것은 MVP 범위 밖 (ACKNOWLEDGED 상태는 확장 예정)
- cmux 통보는 보조적 — inbox 파일이 primary 전달 수단
- 브로커는 동기 처리 — watcher 이벤트 → 브로커 처리 → 다음 이벤트 (MVP에서는 단일 스레드)
