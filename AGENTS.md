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
