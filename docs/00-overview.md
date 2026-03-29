# cmux-agent 작업 계획 개요

## 프로젝트 목적

cmux 기반 멀티 에이전트 플러그인.
cmux workspace 안에서 독립 실행되는 AI CLI들 사이의 메시지를 중개한다.

## 아키텍처 모델

**MSA + Message Queue** 패턴을 따른다.

- 각 AI CLI(Claude Code, Codex CLI, Gemini CLI)는 **독립 마이크로서비스**
- cmux-agent는 **메시지 브로커** — artifact를 감지하고 라우팅
- AI CLI를 감싸거나 stdout을 가로채지 않음
- AI CLI가 결과물(JSON/XML 파일)을 생성하면 **트리거** → 중개

## 시스템 계층 구조

```mermaid
block-beta
    columns 1
    block:gui["cmux GUI 계층"]
        columns 3
        A["workspace / pane 배치"]
        B["상태 표시 / 알림"]
        C["사용자 관찰 인터페이스"]
    end
    block:plugin["cmux-agent 플러그인"]
        columns 4
        D["CLI"]
        E["Watcher"]
        F["Broker"]
        G["Prompting"]
    end
    block:ai["AI CLI 세션 (독립 실행)"]
        columns 3
        H["Claude Code"]
        I["Codex CLI"]
        J["Gemini CLI"]
    end
    block:store["로컬 저장소"]
        columns 4
        K["SQLite 상태"]
        L["JSONL 이벤트"]
        M["outbox"]
        N["inbox"]
    end

    gui --> plugin
    plugin --> store
    ai --> store
```

## 핵심 메시지 흐름

orchestrator와 worker 간의 메시지 중개 흐름이다.
AI CLI는 독립적으로 실행되며, cmux-agent는 파일 기반으로 중개만 수행한다.

```mermaid
sequenceDiagram
    participant U as 사용자
    participant O as Orchestrator<br/>(AI CLI)
    participant OB as outbox/
    participant W as Watcher
    participant B as Broker
    participant IB as inbox/
    participant WK as Worker<br/>(AI CLI)
    participant CX as cmux

    Note over U,CX: 1. 초기화
    U->>CX: cmux-agent start
    CX-->>O: orchestrator pane 생성
    CX-->>WK: worker pane 생성
    U->>O: AI CLI 실행 (직접)
    U->>WK: AI CLI 실행 (직접)

    Note over U,CX: 2. 작업 요청
    U->>O: 작업 요청 (직접 입력)

    Note over U,CX: 3. Dispatch 순환
    O->>OB: dispatch artifact 생성 (JSON)
    W->>OB: 새 파일 감지
    W->>B: artifact 전달
    B->>B: 파싱 · 수신자 결정 · 라우팅
    B->>IB: worker inbox에 메시지 파일 생성
    B->>CX: 알림 (notify / send_text)
    CX-->>WK: 메시지 도착 통보

    Note over U,CX: 4. Result 순환
    WK->>WK: inbox 확인 · 작업 수행
    WK->>OB: result artifact 생성 (JSON)
    W->>OB: 새 파일 감지
    W->>B: artifact 전달
    B->>IB: orchestrator inbox에 결과 전달
    B->>CX: 알림
    CX-->>O: 결과 도착 통보

    Note over U,CX: 5. 반복 또는 완료
    O->>O: 추가 dispatch 또는 완료 판단
```

## 컴포넌트 구조

각 모듈의 책임과 의존 관계이다.

```mermaid
graph TD
    CLI["<b>CLI</b><br/>사용자 명령 인터페이스<br/>start · register · watch<br/>status · events · send"]
    WATCH["<b>Watcher</b><br/>outbox 파일 감시<br/>artifact 감지 · 트리거<br/>watchdog / polling"]
    BROKER["<b>Broker</b><br/>메시지 라우팅<br/>inbox 전달 · 통보<br/>재시도 · 에러 처리"]
    PROMPT["<b>Prompting</b><br/>delivery 메시지 생성<br/>역할별 context 포함<br/>artifact 형식 안내"]
    CMUX["<b>CmuxAdapter</b><br/>cmux GUI 제어<br/>workspace · pane<br/>notify · send_text"]
    STORE["<b>StateStore</b><br/>SQLite 상태 관리<br/>Run · Agent · Message<br/>JSONL 이벤트 로그"]

    CLI --> STORE
    CLI --> CMUX
    CLI --> WATCH
    WATCH --> BROKER
    BROKER --> STORE
    BROKER --> CMUX
    BROKER --> PROMPT
    PROMPT --> STORE
```

## 데이터 모델

run, agent, message의 관계와 상태 전이이다.

```mermaid
erDiagram
    Run ||--o{ Agent : "등록"
    Run ||--o{ Message : "기록"
    Agent ||--o{ Message : "송신/수신"

    Run {
        string run_id PK
        string status
        string workspace_id
        datetime created_at
        datetime updated_at
    }
    Agent {
        string agent_id PK
        string run_id FK
        string role
        string name
        string surface_id
        datetime created_at
    }
    Message {
        string message_id PK
        string run_id FK
        string sender
        string recipient
        string type
        string status
        string payload
        string artifact_path
        datetime created_at
        datetime delivered_at
    }
```

## 상태 전이

### Run 상태

```mermaid
stateDiagram-v2
    [*] --> CREATED: cmux-agent start
    CREATED --> RUNNING: agent 등록 · watcher 시작
    RUNNING --> COMPLETED: 모든 작업 완료
    RUNNING --> FAILED: 복구 불가 오류
    COMPLETED --> [*]
    FAILED --> [*]
```

### Message 상태

```mermaid
stateDiagram-v2
    [*] --> PENDING: artifact 감지 · 큐잉
    PENDING --> DELIVERED: inbox 전달 완료
    PENDING --> FAILED: 전달 실패 (재시도 초과)
    DELIVERED --> ACKNOWLEDGED: AI CLI 수령 확인 (확장 예정)
    DELIVERED --> [*]
    FAILED --> [*]
    ACKNOWLEDGED --> [*]
```

## Artifact 기반 통신 구조

AI CLI와 cmux-agent 사이의 파일 기반 메시지 큐이다.

```mermaid
flowchart LR
    subgraph ai["AI CLI (독립 실행)"]
        O["Orchestrator"]
        W["Worker"]
    end

    subgraph fs["파일 시스템 (.agent/)"]
        OUTBOX["outbox/<br/>AI CLI가 쓰기"]
        INBOX_O["inbox/orchestrator/<br/>Broker가 쓰기"]
        INBOX_W["inbox/worker-1/<br/>Broker가 쓰기"]
        PROC["processed/<br/>처리 완료 보관"]
    end

    subgraph agent["cmux-agent"]
        WATCHER["Watcher<br/>파일 감지"]
        BROKER["Broker<br/>파싱 · 라우팅"]
    end

    O -->|dispatch 생성| OUTBOX
    W -->|result 생성| OUTBOX
    OUTBOX -->|감지| WATCHER
    WATCHER -->|전달| BROKER
    BROKER -->|dispatch 전달| INBOX_W
    BROKER -->|result 전달| INBOX_O
    OUTBOX -.->|처리 후 이동| PROC
    INBOX_W -.->|수령| W
    INBOX_O -.->|수령| O
```

## Watcher → Broker 파이프라인

artifact 감지부터 inbox 전달까지의 상세 흐름이다.

```mermaid
flowchart TD
    START["outbox에 새 파일 생성"]
    DETECT["Watcher: 파일 감지<br/>(watchdog FSEvents)"]
    VALIDATE{"유효성 검증"}
    PARSE["Broker: artifact 파싱<br/>type · sender · recipient 추출"]
    ROUTE{"수신자<br/>등록 확인"}
    DELIVER["inbox/{recipient}/ 에<br/>메시지 파일 생성"]
    NOTIFY["cmux 알림<br/>notify · send_text"]
    RECORD["StateStore 기록<br/>Message DELIVERED"]
    EVENT["이벤트 로그<br/>JSONL 기록"]
    MOVE["outbox → processed/<br/>파일 이동"]
    FAIL_V["processed/failed/ 이동<br/>검증 실패 로그"]
    FAIL_R["FAILED 상태 기록<br/>미등록 agent 로그"]

    START --> DETECT --> VALIDATE
    VALIDATE -->|성공| PARSE --> ROUTE
    VALIDATE -->|실패| FAIL_V
    ROUTE -->|등록됨| DELIVER --> NOTIFY --> RECORD --> EVENT --> MOVE
    ROUTE -->|미등록| FAIL_R
```

## CLI 명령 구조

```mermaid
graph LR
    subgraph run["Run 관리"]
        START["start<br/>run 생성 · workspace · 디렉토리 초기화"]
        STOP["stop<br/>run 종료"]
        STATUS["status<br/>run 상태 조회"]
        EVENTS["events<br/>이벤트 로그 조회"]
    end

    subgraph agent["Agent 관리"]
        REGISTER["register<br/>agent 등록 (이름 · 역할)"]
        AGENTS["agents<br/>등록된 agent 목록"]
    end

    subgraph broker["Broker"]
        WATCH["watch<br/>outbox watcher 시작<br/>(포그라운드 / 데몬)"]
    end

    subgraph msg["메시지"]
        SEND["send<br/>수동 메시지 전송"]
        MESSAGES["messages<br/>메시지 이력 조회"]
    end

    subgraph diag["진단"]
        DOCTOR["doctor<br/>cmux · Python 확인"]
    end
```

## 디렉토리 구조

```mermaid
graph TD
    ROOT[".agent/"]
    DB["control-plane.sqlite3<br/>정규화된 현재 상태"]
    EV["events.jsonl<br/>append-only 이벤트"]
    OB["outbox/<br/>AI CLI → artifact 쓰기"]
    IB["inbox/"]
    IB_O["orchestrator/<br/>orchestrator 수신함"]
    IB_W1["worker-1/<br/>worker-1 수신함"]
    IB_WN["worker-N/<br/>worker-N 수신함"]
    PROC["processed/"]
    PROC_OK["(처리 완료 보관)"]
    PROC_FAIL["failed/<br/>검증 실패 보관"]

    ROOT --> DB
    ROOT --> EV
    ROOT --> OB
    ROOT --> IB
    ROOT --> PROC
    IB --> IB_O
    IB --> IB_W1
    IB --> IB_WN
    PROC --> PROC_OK
    PROC --> PROC_FAIL
```

## 구현 의존성 그래프

기능별 작업 계획의 구현 순서와 의존 관계이다.

```mermaid
graph LR
    M["<b>01</b><br/>Models &<br/>Storage"]
    C["<b>02</b><br/>cmux<br/>Adapter"]
    CLI["<b>03</b><br/>CLI"]
    W["<b>04</b><br/>Watcher"]
    B["<b>05</b><br/>Broker"]
    P["<b>06</b><br/>Prompting"]

    M --> CLI
    M --> W
    M --> B
    C --> CLI
    C --> B
    W --> B
    B --> P
```

## 기능별 작업 계획

| 순서 | 계획 | 설명 | 의존성 |
| --- | --- | --- | --- |
| 1 | [01-models-storage](./01-models-storage.md) | 데이터 모델, SQLite 상태, JSONL 이벤트, inbox/outbox 구조 | 없음 |
| 2 | [02-cmux-adapter](./02-cmux-adapter.md) | cmux 플러그인 인터페이스 (workspace, pane, 알림) | 없음 |
| 3 | [03-cli](./03-cli.md) | CLI 명령어 (run 관리, agent 등록, 상태 조회) | 01, 02 |
| 4 | [04-watcher](./04-watcher.md) | artifact 감지, 파일 시스템 watcher, 트리거 | 01 |
| 5 | [05-broker](./05-broker.md) | 메시지 브로커, 라우팅, inbox/outbox 큐 관리 | 01, 02, 04 |
| 6 | [06-prompting](./06-prompting.md) | 역할별 prompt 생성, delivery 메시지 포매팅 | 05 |

## 초안 참조

`.draft/` 디렉토리에 3개 영역의 초안이 존재한다. 코드는 재사용하지 않으며, 설계 의도와 아키텍처만 참고한다.

| 영역 | 경로 | 설명 |
| --- | --- | --- |
| CLI Control Plane | `.draft/cli/` | 멀티 에이전트 실행 시스템 MVP 초안 |
| Deep Analysis | `.draft/deep-analysis/` | XML 번들링 + 3단계 점진적 리뷰 |
| Dev Automation | `.draft/dev-automation/` | 7계층 로컬 개발 자동화 워크플로우 |

## 핵심 설계 원칙

- **AI CLI는 독립적**: 감싸지 않고, stdout을 가로채지 않음
- **Artifact 기반 트리거**: 파일 생성 → 감지 → 라우팅 (message queue 패턴)
- **cmux-agent = 브로커**: 메시지를 중개할 뿐, AI CLI의 실행에 개입하지 않음
- **GUI ≠ source of truth**: 상태 기준은 SQLite + JSONL
- **provider 무관**: 어떤 AI CLI든 동일한 artifact 형식으로 통신

## 미구현 / 확장 예정

초안에 설계되었으나 MVP 범위 밖인 영역:

| 영역 | 설명 |
| --- | --- |
| Plan Doc 강제 | Plan Doc 없이 execution 단계로 넘어가지 않도록 gate |
| worktree 격리 | 승인된 writer만 지정 worktree에서 수정 |
| single-writer enforcement | 동시 writer 충돌 방지 |
| review / judge / publish | reviewer 세션, judge 판정, fix loop, publish 권한 분리 |
| approval 흐름 | change class 계산, 승인 필요 여부 판정 |
| gate runner | deterministic gate 실행 (lint, typecheck, test) |
| 복구 / 재진입 | 앱 재시작 후 상태 기반 run 재구성 |
| Deep Analysis | XML 번들링 + 3단계 점진적 코드 리뷰 워크플로우 |
| Dev Automation | 7계층 로컬 개발 자동화 전체 워크플로우 |
