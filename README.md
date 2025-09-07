# Patent Chat (Streamlit + Gemini 2.5)

特許出願アイデアを対話で具体化し、特許明細書草案を生成する Web アプリです。

## 要件 / セットアップ
- 必須: Python 3.12, `uv`
- LLM: Google Gemini 2.5（Pro/Flash 切替、Google GenAI SDK 使用）

```bash
# 初回のみ
git clone <THIS_REPO_URL>
cd patent-chat

# 依存関係の同期
uv sync

# 環境変数（.env 推奨）
# GOOGLE_API_KEY=xxxxx   # または GEMINI_API_KEY=xxxxx
# GEMINI_MODEL=gemini-2.5-pro   # 既定モデル（UI から変更可）
```

起動:
```bash
uv run streamlit run app/main.py
```

サイドバーの「Geminiモデル」から Pro/Flash を切替可。タイトル生成には gemini-2.5-flash を使用します。

## プロジェクト構成
- `app/`: コアアプリ
  - `app/main.py`: Streamlit UI とレイアウト
  - `app/state.py`: Dataclass モデルと UI ステート
  - `app/llm.py`: Gemini 連携（フォールバック含む）
  - `app/storage.py`: JSON 永続化（`data/ideas.json`）
  - `app/spec_builder.py`: 会話ヘルパ（仕様生成）
  - `app/export.py`: Word/PDF エクスポート
- `tests/`: Pytest スイート（小さく、振る舞い優先）
- `.github/`: PR テンプレート。`PR_BODY.md` が唯一の真実の情報源（SSOT）
- ドキュメント: `LLM_Prompt_*.md`, `sample.md`
- 設定: `.env`（API キー。コミットしない）

## 開発コマンド
- セットアップ: `uv sync`
- 実行: `uv run streamlit run app/main.py`
- Lint: `uv run ruff check app/`（自動修正: `--fix`）
- Format: `uv run ruff format app/`
- テスト: `uv run pytest -q`（カバレッジ: `--cov=app --cov-report=html`）
- フック: `uv run pre-commit install`（全実行: `uv run pre-commit run --all-files`）

## コーディング規約
- スタイル: 4 スペース、行長 100、import は isort 互換（Ruff）
- 型: 可能な限り型ヒント。公開関数は docstring
- 命名: 関数/変数は `snake_case`、クラスは `PascalCase`、定数は `UPPER_CASE`
- 小さな関数と副作用の最小化、`logging` で記録

## テスト方針
- TDD（Red → Green → Refactor）。失敗するテストから開始
- 配置: `tests/test_*.py`、テスト名は `test_<behavior>`
- 範囲: `state`/`storage`/`spec_builder` のユニットテスト。ネットワーク/LLM はモック
- 実行: `uv run pytest -q` を常にグリーンに維持

## コミット / PR ガイド
- ブランチ: `main` から作成（例: `feature/<name>`、`fix/<name>`）。`main` へ直接コミットしない
- コミット: Conventional Commits（例: `feat: ...`、`fix(llm): ...`）
- PR（日本語・構造化 Markdown）:
  - 作成: `gh pr create --title "feat: ..." --body-file PR_BODY.md`
  - SSOT: `PR_BODY.md` を編集し、`gh pr edit <num> --body-file PR_BODY.md` で同期
  - 含める: 概要/背景/変更点/確認方法/影響範囲/リスク・互換性/関連、テスト結果/スクショ
- クオリティゲート: `uv run pytest -q` と `uv run pre-commit run --all-files` が通過していること

## セキュリティ / 設定
- `.env`（コミットしない）: `GOOGLE_API_KEY` または `GEMINI_API_KEY`、`GEMINI_MODEL`
- 秘密情報はログ出力しない。API 不可時のフォールバックを検証

## Basic 認証（アプリ内）
- 画面表示前に簡易ログインを要求（未設定なら無効）
```dotenv
BASIC_AUTH_USERNAME=your_user
BASIC_AUTH_PASSWORD=your_password
```
- ログイン後はサイドバーから「ログアウト」可能。HTTP レイヤの厳密な Basic 認証が必要な場合は、Nginx 等で `auth_basic` を設定

## 補足
- 初回起動時に `data/ideas.json` 等が自動生成されます
- PDF/Word は簡易テンプレートからエクスポートします
- 質問生成では、質問中に特定の請求項番号（例:「請求項1」）へ言及する場合、その請求項の内容をユーザーが理解しやすいように補足します（多少長くなっても可。必要に応じて1〜2文の説明や例を含め、分かりやすさを優先）
