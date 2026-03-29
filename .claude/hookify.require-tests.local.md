---
name: require-tests
enabled: false
event: stop
action: block
conditions:
    - field: transcript
      operator: not_contains
      pattern: npm test|yarn test|pnpm test|pytest|phpunit|pest|cargo test|go test
---

# TODO : make test, make check 등으로 변경해서 사용

⚠️ **Tests not detected in transcript**

작업 완료 전 테스트 실행이 감지되지 않았습니다.

변경사항이 정상 동작하는지 확인하기 위해, 프로젝트에 맞는 테스트 명령어 중 **하나를 실행**하세요:

- JavaScript/TypeScript: `npm test`, `yarn test`, `pnpm test`
- PHP: `phpunit`, `pest`
- Python: `pytest`
- Go: `go test`
- Rust: `cargo test` 
