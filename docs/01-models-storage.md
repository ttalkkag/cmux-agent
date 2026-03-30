# 01. 데이터 모델 & 상태 저장

## 목적

메시지 브로커의 상태를 관리하는 데이터 모델과 저장 계층을 구현한다.
run, agent, message의 생명주기를 추적하고, inbox/outbox 큐 구조를 제공한다.

## 참조 초안

- `.draft/cli/cmux_agent/models.py` — 데이터 모델 참고
- `.draft/cli/cmux_agent/storage.py` — StateStore 참고
- `.draft/dev-automation/01-detail.md` §L2 — Run Control, State Store

## 데이터 모델

### Run

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| run_id | str | UUID 기반 고유 식별자 |
| status | RunStatus | 생명주기 상태 |
| workspace_id | str | cmux workspace 식별자 |
| created_at | datetime | 생성 시각 |
| updated_at | datetime | 마지막 갱신 시각 |

### RunStatus

```
CREATED → RUNNING → COMPLETED
                  → FAILED
```

### Agent

run에 참여하는 AI CLI를 등록한다. cmux-agent는 AI CLI를 직접 실행하지 않고, 등록된 agent 정보로 메시지를 라우팅한다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| agent_id | str | 고유 식별자 |
| run_id | str | 소속 run |
| role | AgentRole | ORCHESTRATOR / WORKER |
| name | str | 표시 이름 (orchestrator, worker-1 등) |
| surface_id | str? | cmux surface 식별자 (알림/전달용) |
| created_at | datetime | 생성 시각 |

### AgentRole

- `ORCHESTRATOR` — 작업 분해, dispatch 생성
- `WORKER` — 작업 수행, result 생성

### Message

inbox/outbox를 통과하는 모든 메시지를 기록한다.

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| message_id | str | 고유 식별자 |
| run_id | str | 소속 run |
| sender | str | 송신자 agent name |
| recipient | str | 수신자 agent name |
| type | MessageType | DISPATCH / RESULT |
| status | MessageStatus | 큐 상태 |
| payload | str | JSON 직렬화된 메시지 본문 |
| artifact_path | str? | 원본 artifact 파일 경로 |
| created_at | datetime | 생성 시각 |
| delivered_at | datetime? | 전달 완료 시각 |

### MessageType

- `DISPATCH` — orchestrator → worker 작업 위임
- `RESULT` — worker → orchestrator 결과 반환

### MessageStatus

```
PENDING → DELIVERED → ACKNOWLEDGED
        → FAILED
```

## Inbox / Outbox 디렉토리 구조

```
.cmux/
├── control-plane.sqlite3          # 정규화된 현재 상태
├── events.jsonl                   # append-only 이벤트 기록
├── outbox/                        # AI CLI가 artifact를 쓰는 곳
│   ├── {timestamp}-{sender}.json  # watcher가 감지할 파일
│   └── ...
├── inbox/                         # 브로커가 전달할 메시지를 쓰는 곳
│   ├── {recipient}/               # agent별 inbox
│   │   ├── {message_id}.json
│   │   └── ...
│   └── ...
└── processed/                     # 처리 완료된 artifact 보관
    └── ...
```

### Outbox Artifact 형식

AI CLI가 outbox에 생성하는 파일:

```json
{
  "type": "dispatch",
  "sender": "orchestrator",
  "recipient": "worker-1",
  "message": "로그인 API 엔드포인트를 구현하라.",
  "context": {}
}
```

### Inbox Message 형식

브로커가 inbox에 전달하는 파일:

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

## SQLite 상태 저장소 (StateStore)

### 테이블 스키마

```sql
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'CREATED',
    workspace_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE agents (
    agent_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    role TEXT NOT NULL,
    name TEXT NOT NULL,
    surface_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    sender TEXT NOT NULL,
    recipient TEXT NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    payload TEXT NOT NULL,
    artifact_path TEXT,
    created_at TEXT NOT NULL,
    delivered_at TEXT
);
```

### 주요 연산

- `create_run()` → Run 생성
- `update_run_status(run_id, status)` → 상태 전이
- `register_agent(run_id, role, name)` → Agent 등록
- `enqueue_message(run_id, sender, recipient, type, payload)` → 메시지 큐잉
- `mark_delivered(message_id)` → 전달 완료 기록
- `get_pending_messages(recipient)` → 미전달 메시지 조회
- `get_run(run_id)` / `get_latest_run()` → Run 조회
- `get_agents(run_id)` → Agent 목록
- `get_messages(run_id)` → 메시지 이력

## JSONL 이벤트 로그

상태 변경을 append-only로 기록한다.

```json
{"ts": "...", "event": "run.created", "run_id": "abc", "data": {}}
{"ts": "...", "event": "agent.registered", "run_id": "abc", "data": {"name": "orchestrator"}}
{"ts": "...", "event": "artifact.detected", "run_id": "abc", "data": {"path": "outbox/...", "sender": "orchestrator"}}
{"ts": "...", "event": "message.delivered", "run_id": "abc", "data": {"message_id": "...", "recipient": "worker-1"}}
```

## 작업 항목

1. 열거형 정의 (RunStatus, AgentRole, MessageType, MessageStatus)
2. 데이터 클래스 정의 (Run, Agent, Message)
3. StateStore 클래스 — SQLite CRUD
4. JSONL 이벤트 로거
5. inbox/outbox 디렉토리 초기화 유틸리티
6. 단위 테스트

## 설계 참고

- outbox는 AI CLI가 쓰고 watcher가 읽는다 — 한 방향
- inbox는 브로커가 쓰고 AI CLI가 읽는다 — 한 방향
- processed 디렉토리로 이동하여 중복 처리 방지
- 모든 시각은 UTC ISO 8601
