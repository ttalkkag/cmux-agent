# 02. cmux 어댑터

## 목적

cmux GUI와 통신하는 플러그인 인터페이스를 구현한다.
workspace, pane 관리와 알림/통보 기능을 제공한다.

## 참조 초안

- `.draft/cli/cmux_agent/cmux.py` — CmuxAdapter 참고
- `.draft/cli/plan.md` §5 — cmux 설계상 중요한 사실

## cmux 제어 범위

### 책임

- workspace, pane 생성과 정리
- 사람이 보는 AI CLI 대화 관찰 환경 제공
- 알림 (메시지 도착, 작업 완료 등)
- 메시지 전달 시 pane에 통보 (send_text)

### 비책임

- AI CLI 프로세스 실행/관리 (AI CLI는 독립)
- run 상태 저장 (→ StateStore)
- 메시지 저장/라우팅 (→ 브로커)

## 주요 인터페이스

### Workspace 관리

```python
create_workspace(name: str) -> str          # workspace_id 반환
close_workspace(workspace_id: str) -> None
list_workspaces() -> list[dict]
```

### Pane 관리

```python
create_pane(workspace_id: str, name: str) -> str    # surface_id
focus_pane(surface_id: str) -> None
close_pane(surface_id: str) -> None
list_surfaces(workspace_id: str) -> list[dict]
```

### 통보 / 알림

```python
send_text(surface_id: str, text: str) -> None   # pane에 텍스트 주입 (통보용)
notify(title: str, body: str) -> None            # macOS 알림
set_status(surface_id: str, status: str) -> None # sidebar metadata
```

### 유틸리티

```python
is_available() -> bool                          # cmux 설치 확인
identify(surface_id: str) -> dict               # pane 정보 조회
```

## 구현 방식

cmux CLI 명령을 subprocess로 실행한다.
초기에는 CLI 기반, 필요 시 Unix socket API로 전환.

## 기본 레이아웃

```
┌─────────────────┬──────────────────┐
│  orchestrator   │  worker-1        │
│  (AI CLI)       │  (AI CLI)        │
│  [기본 포커스]  │                  │
│                 ├──────────────────┤
│                 │  worker-2 (동적) │
│                 │                  │
└─────────────────┴──────────────────┘
```

## 작업 항목

1. CmuxAdapter 클래스 구현
2. workspace CRUD
3. pane 관리
4. send_text, notify, set_status
5. cmux 설치 확인 (doctor)
6. 기본 레이아웃 생성 헬퍼
7. 단위 테스트 (subprocess mock)

## 설계 참고

- cmux-agent는 플러그인 — cmux의 기능을 활용할 뿐, cmux를 수정하지 않음
- send_text는 AI CLI에 직접 명령을 주입하는 게 아니라, 메시지 도착을 **통보**하는 용도
- AI CLI는 inbox 파일을 읽어서 작업을 수령 — send_text는 보조적 알림
- cmux 의존성을 이 어댑터에서 격리 — 나머지 코드는 cmux를 직접 호출하지 않음
