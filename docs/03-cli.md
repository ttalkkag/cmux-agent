# 03. CLI 명령어

## 목적

cmux-agent 플러그인의 CLI 인터페이스를 구현한다.
run 관리, agent 등록, 브로커 시작, 상태 조회 명령을 제공한다.

## 참조 초안

- `.draft/cli/cmux_agent/cli.py` — CLI 구조 참고
- `.draft/diagram.md` — CLI 명령 요약

## 진입점

```toml
[project.scripts]
cmux-agent = "cmux_agent.cli:main"
```

## 명령어 구조

### 초기화 & 진단

```bash
cmux-agent doctor                    # cmux 설치 확인, .agent 디렉토리 확인
```

### Run 관리

```bash
cmux-agent start                     # 새 run 시작 (workspace + outbox/inbox 초기화)
cmux-agent stop [run_id]             # run 종료
cmux-agent status [run_id]           # run 상태 조회
cmux-agent events [run_id]           # 이벤트 로그 조회
```

### Agent 등록

```bash
cmux-agent register <name> --role <orchestrator|worker>   # agent 등록
cmux-agent agents [run_id]                                 # 등록된 agent 목록
```

### 브로커

```bash
cmux-agent watch                     # outbox watcher 시작 (포그라운드)
cmux-agent watch --daemon            # 백그라운드 데몬으로 시작
```

### 메시지

```bash
cmux-agent send <recipient> "<message>"    # 수동 메시지 전송 (테스트/디버깅용)
cmux-agent messages [run_id]               # 메시지 이력 조회
```

## 명령어 상세

### `doctor`

시스템 요구사항을 검증한다.

- cmux 설치 여부
- Python 버전 (3.9+)
- .agent 디렉토리 쓰기 권한

### `start`

1. run_id 생성
2. `.agent/` 디렉토리 초기화 (outbox, inbox, processed)
3. SQLite 초기화, Run 레코드 생성
4. cmux workspace 생성
5. 기본 pane 생성 (orchestrator, worker-1)
6. watcher 자동 시작 (선택)

### `register`

AI CLI가 실행되는 pane을 agent로 등록한다.

1. 이름 중복 확인
2. Agent 레코드 생성
3. inbox/{name}/ 디렉토리 생성
4. cmux surface_id 연결 (선택)

### `watch`

outbox 디렉토리를 감시하여 artifact를 감지하고 라우팅한다.

- 파일 생성 이벤트 감지
- artifact 파싱 → 수신자 결정 → inbox에 전달
- 처리 완료된 파일은 processed/로 이동
- 포그라운드 또는 데몬 모드

### `status`

```
Run: abc-123
Status: RUNNING
Workspace: run-abc-123

Agents:
  orchestrator  | ORCHESTRATOR
  worker-1      | WORKER
  worker-2      | WORKER

Messages:
  3 delivered, 1 pending
```

### `events`

```
10:00:00  run.created         run_id=abc-123
10:00:01  agent.registered    name=orchestrator
10:00:05  artifact.detected   sender=orchestrator → worker-1
10:00:06  message.delivered   recipient=worker-1
```

## run_id 자동 감지

run_id를 명시하지 않으면 가장 최근 활성 run을 자동으로 사용한다.

## 작업 항목

1. CLI 엔트리포인트 및 argparse 설정
2. `doctor` 명령
3. `start` 명령 (run 생성 + workspace + 디렉토리 초기화)
4. `stop` 명령
5. `register` 명령 (agent 등록)
6. `agents` 명령 (agent 목록)
7. `watch` 명령 (watcher 시작)
8. `status` / `events` 명령
9. `send` / `messages` 명령
10. run_id 자동 감지
11. 단위 테스트

## 설계 참고

- argparse 사용 (외부 의존성 최소화)
- AI CLI를 실행하는 명령은 없음 — AI CLI는 사용자가 직접 실행
- `watch`가 핵심 — 이것이 메시지 브로커 역할
- 에러 시 종료 코드 1, 명확한 에러 메시지
