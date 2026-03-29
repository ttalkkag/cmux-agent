# cmux-agent

cmux 기반 멀티 에이전트 메시지 브로커.
독립 실행되는 AI CLI(Claude Code, Codex CLI, Gemini CLI) 사이의 메시지를 자동으로 중개한다.

## 요구사항

- macOS + [cmux](https://cmux.com)
- Python 3.11+
- AI CLI 1개 이상 (claude, codex, gemini)

## 설치

```bash
uv sync                        # 의존성 설치
uv tool install --editable .   # cmux-agent 명령어 등록
```

## 설정

프로젝트 루트에 `cmux-agent.json`을 생성하여 agent별 AI CLI를 지정한다.
파일이 없으면 orchestrator + worker-1 (모두 claude)이 기본값이다.

```json
{
  "orchestrator": "claude",
  "worker-1": "claude",
  "worker-2": "codex",
  "worker-3": "gemini"
}
```

worker 수는 설정 파일의 `worker-N` 키 개수에 따라 동적으로 결정된다.

## 사용법

### 1. Run 시작

```bash
cmux-agent
```

cmux workspace에 탭이 생성된다: controller, orchestrator, worker-1, ...

- controller: watcher가 자동 실행됨
- orchestrator, worker-N: 설정 파일에 지정된 AI CLI가 자동 실행됨
- 각 AI CLI에 역할과 프로토콜(artifact 형식, 경로)이 사전 주입됨

### 2. 작업 요청

```bash
cmux-agent task "사용자 인증 시스템을 구현하라"
```

orchestrator AI CLI에 작업이 자동 주입된다. 이후 자율 순환이 시작된다.

### 3. 자율 순환

사용자 개입 없이 orchestrator와 worker가 자동으로 작업을 주고받는다.

```
사용자: cmux-agent task "인증 시스템 구현"
  ↓ send_text (orchestrator 터미널에 자동 주입)
orchestrator AI CLI: 작업 분석 → .agent/outbox/ 에 dispatch artifact 생성
  ↓ watcher 감지
broker: 파싱 → worker-1 inbox 전달 + send_text (worker 터미널에 자동 주입)
  ↓
worker-1 AI CLI: 작업 수행 → .agent/outbox/ 에 result artifact 생성
  ↓ watcher 감지
broker: 파싱 → orchestrator inbox 전달 + send_text (orchestrator 터미널에 자동 주입)
  ↓
orchestrator AI CLI: 결과 확인 → 추가 dispatch 또는 완료 보고
```

닫힌 탭의 worker는 자동으로 감지되어 작업 대상에서 제외된다.

### 4. 상태 확인

```bash
cmux-agent status              # run 상태 조회
cmux-agent agents              # 등록된 agent 목록
cmux-agent events              # 이벤트 로그
cmux-agent messages            # 메시지 이력
cmux-agent stop                # run 종료
```

## Artifact 형식

### Dispatch (orchestrator → worker)

```json
{
  "type": "dispatch",
  "sender": "orchestrator",
  "recipient": "worker-1",
  "message": "구체적인 작업 지시"
}
```

### Result (worker → orchestrator)

```json
{
  "type": "result",
  "sender": "worker-1",
  "recipient": "orchestrator",
  "message": "작업 결과 요약"
}
```

## 기타 명령어

```bash
cmux-agent doctor              # 시스템 진단
cmux-agent send <agent> "msg"  # 수동 메시지 전송 (테스트용)
cmux-agent register <name> --role worker  # agent 추가 등록
```

## 디렉토리 구조

```
.agent/
├── control-plane.sqlite3   # 상태 저장소
├── events.jsonl            # 이벤트 로그
├── ORCHESTRATOR.md         # orchestrator 프로토콜 파일
├── WORKER-1.md             # worker-1 프로토콜 파일
├── outbox/                 # AI CLI가 artifact를 생성하는 곳
├── inbox/                  # 브로커가 메시지를 전달하는 곳
│   ├── orchestrator/
│   ├── worker-1/
│   └── ...
└── processed/              # 처리 완료된 artifact 보관
```

## 테스트

```bash
uv run pytest
```
