# 브랜치명 검증 가이드

**실행 시점**: `git push` 시 (푸시 전)
**스크립트**: `.husky/validate-branch.cjs`
**형식**: `<type>/<description>` 또는 `<type>/<segment>/<segment>/...` (depth 제한 없음)
**허용 문자**: 소문자(a-z), 숫자(0-9), 하이픈(-), 점(.), 언더바(_)

## 보호 브랜치 (직접 푸시 허용)

`main`, `master`, `develop`, `staging`

## 브랜치명 형식

### ✅ 올바른 형식

```bash
feature/user-authentication
fix/404-error
copilot/add-validation
claude/refactor-api
hotfix/security-patch-2024
release/1.0.0
feature/frontend/user-authentication
fix/api/null-response
refactor/backend/auth-logic
docs/api/endpoint-guide
test/integration/payment-flow
dependabot/npm_and_yarn/turbo-2.7.3
dependabot/npm_and_yarn/tailwindcss/postcss-4.1.18
```

### ❌ 잘못된 형식

```bash
Feature/Frontend/User-auth  # 대문자 사용 금지
my-feature                  # 타입 누락
feature/                    # 설명 누락
```

## 작명 규칙

1. **소문자만 사용**: `Feature` ❌ → `feature` ✅
2. **명확한 설명**: `fix/bug` ❌ → `fix/login-validation-error` ✅
3. **하이픈으로 단어 구분**: `userauth` ❌ → `user-authentication` ✅
4. **간결하게**: `feature/add-new-user-authentication-system-for-web` ❌
   → `feature/user-authentication` ✅

## 검증 우회

```bash
# 긴급 상황에서만 사용
git push --no-verify
```

⚠️ **주의**: GitHub Actions에서는 우회할 수 없으므로 규칙을 준수하세요.

## 다중 검증 계층

| 계층             | 시점              | 우회 가능 여부                   |
|----------------|-----------------|----------------------------|
| 로컬 Husky       | `git push` 실행 시 | ✅ `--no-verify` 플래그로 우회 가능 |
| GitHub Actions | PR 생성/수정 시      | ❌ 필수 체크 (우회 불가)            |

GitHub Actions 검증은 `.github/workflows/branch-name-check.yml`에서 실행됩니다.
