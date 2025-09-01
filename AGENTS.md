# Repository Guidelines

## Project Structure & Module Organization
- `app/`: Core app code
  - `main.py`: Streamlit UI and layout
  - `state.py`: Dataclass models and UI state
  - `llm.py`: Gemini integration with fallbacks
  - `storage.py`: JSON persistence (`data/ideas.json`)
  - `spec_builder.py`: Conversation helpers
  - `export.py`: Word/PDF exporters
- `tests/`: Pytest suite (behavior-first, small focused tests)
- `.github/`: PR templates; `PR_BODY.md` is PR SSOT
- Docs: `LLM_Prompt_*.md`, `sample.md`
- Config: `.env` for API keys (not committed)

## Build, Test, and Development Commands
- Setup: `uv sync` — install dependencies (Python 3.12 via uv)
- Run app: `uv run streamlit run app/main.py`
- Lint: `uv run ruff check app/` (fix: `--fix`)
- Format: `uv run ruff format app/`
- Tests: `uv run pytest -q` (coverage: `--cov=app --cov-report=html`)
- Hooks: `uv run pre-commit install`; run all `uv run pre-commit run --all-files`

## Coding Style & Naming Conventions
- Style: 4-space indent, line length 100 (Ruff), sorted imports (isort via Ruff)
- Types: Prefer type hints; docstrings for public functions
- Naming: `snake_case` for modules/functions, `PascalCase` for classes, `UPPER_CASE` for constants
- Keep functions small and side-effect aware; log via `logging`

## Testing Guidelines
- Philosophy: TDD (Red → Green → Refactor). Write a failing test first.
- Layout: `tests/test_*.py`; test names `test_<behavior>`
- Scope: Unit tests for `state`, `storage`, `spec_builder`; mock network/LLM calls
- Run locally: `uv run pytest -q`; keep tests and linting green before PR

## Commit & Pull Request Guidelines
- Branching: create from `main` (e.g., `feature/<name>`, `fix/<name>`). Do not commit to `main`.
- Commits: Conventional Commits style (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`; optional scope: `fix(llm): ...`).
- PRs: Use GitHub CLI and Japanese, structured Markdown.
  - Create: `gh pr create --title "feat: ..." --body-file PR_BODY.md`
  - Keep `PR_BODY.md` as SSOT; sync with `gh pr edit <num> --body-file PR_BODY.md`
  - Include: 概要/背景/変更点/確認方法/影響範囲/リスク・互換性/関連、テスト結果/スクショ
- Quality gates: `uv run pytest -q` and `uv run pre-commit run --all-files` must pass

## Security & Configuration
- `.env` (not committed): `GOOGLE_API_KEY` or `GEMINI_API_KEY`, `GEMINI_MODEL`
- Avoid logging secrets; validate graceful fallbacks when API unavailable
