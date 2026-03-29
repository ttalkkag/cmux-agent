# 04. Artifact Watcher

## 목적

outbox 디렉토리를 감시하여 AI CLI가 생성한 artifact를 감지하고 트리거한다.
메시지 큐의 consumer 역할.

## 참조 초안

- `.draft/dev-automation/01-detail.md` §L2 — Run Control, 이벤트 기반 처리
- `.draft/diagram.md` — 메시지 라우팅 흐름

## 감지 대상

```
.agent/outbox/
├── 1711698000-orchestrator-dispatch.json
├── 1711698005-worker-1-result.json
└── ...
```

AI CLI가 outbox에 JSON/XML 파일을 생성하면, watcher가 감지하여 브로커에 전달한다.

## Watcher 동작 흐름

```
watcher 시작
  → outbox 디렉토리 감시
  → 새 파일 감지
  → 파일 읽기 + 유효성 검증
  → 브로커에 이벤트 전달 (artifact_detected)
  → 처리 완료된 파일을 processed/로 이동
  → 이벤트 로그 기록
```

## 구현 방식

### 옵션 1: 파일 시스템 이벤트 (권장)

macOS의 FSEvents를 활용하는 watchdog 라이브러리 사용.

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ArtifactHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.src_path.endswith('.json'):
            self.process_artifact(event.src_path)
```

- 실시간 감지 (지연 최소)
- CPU 부하 낮음
- 외부 의존성 1개 (watchdog)

### 옵션 2: 폴링

주기적으로 outbox 디렉토리를 스캔.

```python
while running:
    new_files = scan_outbox()
    for f in new_files:
        process_artifact(f)
    sleep(interval)
```

- 외부 의존성 없음
- 폴링 간격만큼 지연 발생
- fallback으로 유지

## Artifact 유효성 검증

1. 파일 확장자 확인 (.json 또는 .xml)
2. 파일 크기 확인 (빈 파일, 비정상 대용량 파일 거부)
3. JSON/XML 파싱 가능 여부
4. 필수 필드 존재 확인 (type, sender, recipient, message)
5. sender가 등록된 agent인지 확인
6. recipient가 등록된 agent인지 확인

### 검증 실패 시

- 경고 로그 기록
- 파일을 processed/failed/로 이동
- 이벤트 로그에 기록 (artifact.validation_failed)

## 파일 처리 안전성

### 원자적 쓰기 문제

AI CLI가 파일을 쓰는 중에 watcher가 읽으면 불완전한 데이터를 처리할 수 있다.

**해결 방법**:
- 임시 파일명으로 쓰고 rename (rename은 원자적)
- 또는 `.tmp` 확장자 → `.json` 확장자로 rename
- watcher는 `.json`/`.xml` 파일만 감시

### 중복 처리 방지

- 처리 완료된 파일은 processed/로 이동
- StateStore에 artifact_path 기록 → 중복 확인
- watcher 재시작 시 이미 처리된 파일은 무시

## Watcher 클래스

```python
class ArtifactWatcher:
    def __init__(self, outbox_path: str, broker: MessageBroker):
        ...

    def start(self) -> None:
        """감시 시작 (포그라운드)"""

    def stop(self) -> None:
        """감시 중지"""

    def process_artifact(self, file_path: str) -> None:
        """artifact 파일을 읽고 브로커에 전달"""

    def validate_artifact(self, data: dict) -> bool:
        """artifact 유효성 검증"""
```

## 작업 항목

1. ArtifactWatcher 클래스 골격
2. 파일 시스템 감시 구현 (watchdog 기반)
3. 폴링 fallback 구현
4. artifact 유효성 검증
5. 처리 완료 파일 이동 (processed/)
6. 검증 실패 처리 (processed/failed/)
7. 이벤트 로그 연동
8. 중복 처리 방지
9. graceful shutdown
10. 단위 테스트

## 설계 참고

- watcher는 outbox만 감시 — inbox는 브로커가 직접 관리
- AI CLI가 어떤 provider인지 watcher는 모름 — artifact 형식만 확인
- watcher는 메시지 내용을 해석하지 않음 — 파싱과 라우팅은 브로커에 위임
- `cmux-agent watch` 명령으로 시작, Ctrl+C로 종료 또는 데몬 모드
