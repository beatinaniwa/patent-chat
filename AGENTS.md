# AGENTS.md

## CRITICAL DEVELOPMENT RULES (MUST FOLLOW)

1. **Test-Driven Development (TDD)**: Always follow t-wada's recommended TDD practices:
   - Write tests FIRST before implementing any feature
   - Follow the Red-Green-Refactor cycle strictly
   - Tests should be minimal and focused on behavior
   - No production code without a failing test first

2. **Branch Management**: NEVER work directly on main branch:
   - Always create a new branch from main before starting work
   - Use descriptive branch names (e.g., `feature/add-export`, `fix/api-error-handling`)
   - Create pull requests for all changes

3. **GitHub CLI Usage**: Utilize `gh` command extensively:
   - Create PRs: `gh pr create`
   - Check PR status: `gh pr status`
   - View issues: `gh issue list`
   - Create branches and manage workflow through gh commands

4. **Pull Request Descriptions (日本語・Markdown)**:
   - PRのタイトル・本文は、原則として「わかりやすい日本語」で記述する
   - 本文はMarkdownで構造化し、見出し・箇条書きで要点を簡潔に示す
   - 推奨セクション: 概要 / 背景 / 変更点 / 確認方法 / 影響範囲 / リスク・互換性 / 関連
   - 具体的・検証可能な情報（再現手順・テスト結果・スクリーンショットやログ等）を含める
   - PR本文は `PR_BODY.md` を唯一のソース（SSOT）として管理する
   - 作成時は必ず `--body-file PR_BODY.md` を使用してPRを作成する
   - 変更が生じたら都度 `gh pr edit <number> --body-file PR_BODY.md` で本文を同期する（Web上での直接編集は禁止）
   - 共通テンプレート: `/.github/PULL_REQUEST_TEMPLATE.md`
   - 用途別テンプレート: `/.github/PULL_REQUEST_TEMPLATE/feature.md`, `/.github/PULL_REQUEST_TEMPLATE/bug.md`
   - 個別の長文は `pr/yyyymmdd-*.md` 等で管理し `.gitignore` で除外

   例（テンプレート）:

   ```md
   ### 概要
   変更の一文サマリ。

   ### 背景
   なぜこの変更が必要か（課題・不具合・要件）。

   ### 変更点
   - 主要なコード変更（ファイル単位で箇条書き）

   ### 確認方法
   1. 自動テストの実行コマンドと期待結果
   2. 手動確認手順（スクリーンショット/ログがあれば添付）

   ### 影響範囲
   影響を受ける機能・非機能（パフォーマンス/セキュリティ等）。

   ### リスク・互換性
   既存利用者への互換性、ロールバック方法、フォント/依存関係など。

   ### 関連
   関連するIssue/PR/ドキュメントへのリンク。
   ```

### Pull Request 運用チェックリスト（必須）
- [ ] `PR_BODY.md` を最新内容に更新した
- [ ] `gh pr create --title "..." --body-file PR_BODY.md` または `gh pr edit <number> --body-file PR_BODY.md` で本文を同期した
- [ ] 概要/背景/変更点/確認方法/影響範囲/リスク・互換性/関連 が埋まっている
- [ ] 自動テストがグリーン（`uv run pytest -q`）・Lint/Format がOK（`uv run pre-commit run --all-files`）
- [ ] UI/UXの変更はスクリーンショット/ログを添付
- [ ] 影響範囲と互換性・ロールバック方法を明記


## Project Overview

Patent Chat is a Streamlit web application that helps users draft patent specifications through interactive dialogue with Google Gemini 2.5 Pro. The system generates patent drafts based on user ideas and iteratively refines them through a Q&A process.

## Development Commands

### Git Workflow with GitHub CLI
```bash
# Create new feature branch from main
git checkout main
git pull origin main
git checkout -b feature/your-feature-name

# After implementation, create PR
gh pr create --title "Feature: Description" --body "Details..."

# Check PR status
gh pr status

# View and manage issues
gh issue list
gh issue view <number>
gh issue create --title "Bug: Description"

# Review PRs
gh pr list
gh pr checkout <number>
gh pr review <number> --approve
```

### Environment Setup
```bash
# Install dependencies using uv
uv sync

# Activate virtual environment (uv manages .venv automatically)
source .venv/bin/activate  # or let uv handle it automatically
```

### Running the Application
```bash
# Start development server
uv run streamlit run app/main.py

# Alternative: Run with activated venv
streamlit run app/main.py
```

### Code Quality
```bash
# Run linter (Ruff)
uv run ruff check app/
uv run ruff check app/ --fix  # Auto-fix issues

# Format code
uv run ruff format app/

# Run pre-commit hooks manually
uv run pre-commit run --all-files

# Install pre-commit hooks (for automatic checking on git commit)
uv run pre-commit install
```

### Testing (TDD Workflow)
```bash
# TDD Cycle: Red → Green → Refactor

# 1. RED: Write failing test first
uv run pytest tests/test_new_feature.py -v  # Should fail

# 2. GREEN: Write minimal code to pass
uv run pytest tests/test_new_feature.py -v  # Should pass

# 3. REFACTOR: Improve code while keeping tests green
uv run pytest  # Run all tests to ensure nothing broke

# Run tests with coverage
uv run pytest --cov=app --cov-report=html

# Run specific test file
uv run pytest tests/test_example.py -v

# Run tests matching pattern
uv run pytest -k "test_pattern" -v
```

## Architecture & Key Components

### Core Modules

- **app/main.py**: Streamlit entry point. Manages UI layout with sidebar for idea list and main area for idea editing/hearing/draft display. Uses st.session_state for state management.

- **app/state.py**: Defines data models using dataclasses:
  - `Idea`: Stores patent idea with title, category, description, conversation messages, draft markdown, and version
  - `AppState`: UI state management (selected idea, form visibility)

- **app/llm.py**: Gemini API integration layer:
  - `generate_title()`: Creates concise titles from idea descriptions (uses flash model for speed)
  - `bootstrap_spec()`: Generates initial patent draft from idea and instruction document
  - `next_questions()`: Generates 3-5 yes/no questions based on draft and instructions
  - `regenerate_spec()`: Regenerates entire draft from scratch using idea, Q&A history, and instructions (v2+)
  - `refine_spec()`: Updates draft based on user answers to questions (deprecated, kept for compatibility)
  - Includes fallback logic when API is unavailable

- **app/storage.py**: JSON-based persistence layer for ideas in `data/ideas.json`

- **app/spec_builder.py**: Helper functions for managing conversation history

- **app/export.py**: Document export functionality (Word/PDF)

### Key Files

- **LLM_Prompt_for_Patent_Application_Drafting_from_Idea.md**: Primary instruction document for patent drafting (prioritized over sample.md)
- **sample.md**: Fallback instruction document with patent specification structure
- **data/ideas.json**: Local storage for all patent ideas and drafts

## Environment Variables

Required in `.env` file:
- `GOOGLE_API_KEY` or `GEMINI_API_KEY`: API key for Google Gemini
- `GEMINI_MODEL`: Model for specification generation (default: gemini-2.5-pro)
- `GEMINI_TITLE_MODEL`: Model for title generation (default: gemini-2.5-flash)

## Workflow

1. User creates new idea → Title generated → Initial draft created → First questions generated
2. User answers questions (yes/no radio buttons) → Draft completely regenerates from all information
3. Draft displayed above, Q&A hearing section below
4. Each answer triggers full draft regeneration and new question generation
5. User can export final draft to Word/PDF

## Important Patterns

- State management uses Streamlit's st.session_state extensively
- All API calls include error handling with fallback behavior
- Questions are limited to 5 max, displayed as radio buttons for yes/no answers
- Draft regeneration happens automatically after each answer
- Logging to terminal for debugging (via Python logging module)
