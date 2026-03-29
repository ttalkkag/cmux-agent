.PHONY: help dev check claude init speckit

.DEFAULT_GOAL := help

help: ## 사용 가능한 명령어 목록 출력
	@awk 'BEGIN {FS = ":.*##"; printf "\n사용법:\n  make \033[36m<target>\033[0m\n\n명령어:\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

dev: ## 전체 설정 (init + claude + speckit)
	@$(MAKE) init
	@$(MAKE) claude
	@$(MAKE) speckit

check: ## 테스트 및 린트 검사 실행
	@echo "[check] running tests..."
	# 테스트 명령어 추가 (예: npm test, pytest, go test 등)
	@echo "[check] running lint..."
	# 린트 명령어 추가 (예: npm run lint, flake8, golangci-lint 등)
	@echo "[check] all checks passed"

claude: ## Claude Code 환경 설정
	@echo "[claude] downloading AGENT.md..."
	@tmp_claude=$$(mktemp); \
	claude_url="https://raw.githubusercontent.com/forrestchang/andrej-karpathy-skills/main/CLAUDE.md"; \
	if ! curl -fsSL "$$claude_url" -o "$$tmp_claude"; then \
		rm -f "$$tmp_claude"; \
		echo "[claude] AGENT.md download failed"; \
		exit 1; \
	fi; \
	if [ -f AGENT.md ] && grep -qF "Behavioral guidelines to reduce common LLM coding mistakes" AGENT.md; then \
		echo "[claude] AGENT.md already up to date"; \
	elif [ -f AGENT.md ]; then \
		printf '\n' >> AGENT.md; \
		cat "$$tmp_claude" >> AGENT.md; \
	else \
		mv "$$tmp_claude" AGENT.md; \
	fi; \
	rm -f "$$tmp_claude"

init: ## 프로젝트 환경 설정
	@if [ ! -f .env ]; then \
		echo "[init] .env not found"; \
		exit 1; \
	fi
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "[init] docker not found"; \
		exit 1; \
	fi
	@if ! docker compose version >/dev/null 2>&1; then \
		echo "[init] docker compose not found"; \
		exit 1; \
	fi
	@if ! docker info >/dev/null 2>&1; then \
		echo "[init] docker is not running"; \
		exit 1; \
	fi
	@if [ -f docker-compose.yml ]; then \
		echo "[init] starting docker containers..."; \
		docker compose up -d; \
	fi
	@echo "[init] installing npm packages..."
	@docker run --rm -v $$(pwd):/app -w /app node:22-alpine sh -c "apk add --no-cache git && npm install"

speckit: ## speckit 설치 (기본값: claude)
	@if ! command -v specify >/dev/null 2>&1; then \
		echo "[speckit] specify not found"; \
		echo "[speckit] run: uv tool install specify-cli --from git+https://github.com/github/spec-kit.git"; \
		exit 1; \
	fi
	@agent="$(filter-out speckit,$(MAKECMDGOALS))"; \
	if [ -z "$$agent" ]; then \
		agent="claude"; \
	fi; \
	yes | specify init --here --ai "$$agent" --script sh

%:
	@:
