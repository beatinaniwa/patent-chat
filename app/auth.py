from __future__ import annotations

import os
import secrets
from typing import Optional


def _get_env_user_pass() -> tuple[Optional[str], Optional[str]]:
    """Fetch Basic auth credentials from environment variables.

    Enabled when both `BASIC_AUTH_USERNAME` and `BASIC_AUTH_PASSWORD` are set.
    """
    return os.getenv("BASIC_AUTH_USERNAME"), os.getenv("BASIC_AUTH_PASSWORD")


def is_basic_auth_enabled() -> bool:
    """Return True if Basic auth is enabled via env vars."""
    user, pwd = _get_env_user_pass()
    return bool(user and pwd)


def verify_credentials(username: str, password: str) -> bool:
    """Constant-time compare for provided credentials vs env.

    Uses `secrets.compare_digest` to reduce timing side-channel risk.
    """
    env_user, env_pwd = _get_env_user_pass()
    if env_user is None or env_pwd is None:
        return False
    return secrets.compare_digest(username or "", env_user) and secrets.compare_digest(
        password or "", env_pwd
    )


def render_login_gate(st) -> None:
    """Render a blocking login form if Basic auth is enabled and not authenticated.

    Sets `st.session_state["auth_user"]` on success and stops execution until
    authentication passes. Call this at the top of `main()`.
    """
    if not is_basic_auth_enabled():
        return

    # Already authenticated
    if st.session_state.get("auth_user"):
        return

    st.title("🔒 認証が必要です")
    st.caption("管理者から共有されたユーザー名とパスワードを入力してください。")

    with st.form("login-form", clear_on_submit=False):
        username = st.text_input("ユーザー名", value="", autocomplete="username")
        password = st.text_input(
            "パスワード", value="", type="password", autocomplete="current-password"
        )
        submitted = st.form_submit_button("ログイン", type="primary")

        if submitted:
            if verify_credentials(username, password):
                st.session_state["auth_user"] = username
                st.success("ログインしました。")
                st.rerun()
            else:
                st.error("ユーザー名またはパスワードが正しくありません。")

    # Block the rest of the app until login succeeds
    st.stop()


def render_sidebar_user(st) -> None:
    """Render sidebar user section with logout when auth is enabled."""
    if not is_basic_auth_enabled():
        return
    user = st.session_state.get("auth_user")
    with st.sidebar:
        if user:
            st.caption(f"ログイン中: {user}")
            if st.button("ログアウト", use_container_width=True):
                # Clear auth state and refresh
                st.session_state.pop("auth_user", None)
                st.rerun()
        else:
            st.caption("未ログイン")
