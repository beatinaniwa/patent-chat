# Patent Chat (Streamlit + Gemini 2.5 Pro)

特許出願アイデアを対話で具体化し、特許明細書草案を生成する Web アプリです。

## 要件
- Python 3.12
- パッケージ管理: uv
- LLM: Google Gemini 2.5 Pro（Google GenAI SDK）

## セットアップ
```bash
# リポジトリ取得（初回）
git clone <THIS_REPO_URL>
cd patent-chat

# 依存関係同期
uv sync

# 環境変数設定（例）
# .env に以下を設定するか、shell に export してください
# GOOGLE_API_KEY=xxxxx  # または GEMINI_API_KEY=xxxxx
```

## 開発サーバ起動
```bash
uv run streamlit run app/main.py
```

## 構成
- `app/main.py`: Streamlit エントリポイント
- `app/state.py`: アプリ全体の状態管理（SessionState）
- `app/storage.py`: アイデアとセッションの永続化層（ローカル JSON）
- `app/llm.py`: Gemini 2.5 Pro API ラッパ（google-genai）
- `app/spec_builder.py`: 特許明細作成ロジック（質問計画・生成）
- `app/export.py`: Word/PDF 出力
- `sample.md`: 特許明細作成手順書
- `uv.lock` / `pyproject.toml`: 依存管理

## 環境変数
- `GOOGLE_API_KEY`: Gemini 用 API キー

## メモ
- 初回起動時に `data/ideas.json` 等が自動生成されます。
- PDF/Word 生成は簡易テンプレートからエクスポートします。
