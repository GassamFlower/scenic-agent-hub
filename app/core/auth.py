"""
管理后台 — 简单认证模块。

MVP 阶段只需要一个管理员账号：
- 用户名：admin（固定）
- 密码：从环境变量 ADMIN_PASSWORD 读取
- 未设置时使用默认密码（部署时务必修改）
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

# ── 配置 ────────────────────────────────────────────────────

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123456")

# 简单 Token 存储（生产环境应换 Redis/JWT）
_tokens: dict[str, datetime] = {}
TOKEN_EXPIRE_HOURS = 24


# ── 核心函数 ────────────────────────────────────────────────


def verify_admin(username: str, password: str) -> bool:
    """校验管理员账号密码。"""
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def create_token() -> str:
    """生成并存储一个管理后台访问 Token。"""
    token = secrets.token_hex(32)
    _tokens[token] = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    return token


def verify_token(token: Optional[str]) -> bool:
    """校验 Token 有效性。"""
    if not token:
        return False
    expire = _tokens.get(token)
    if not expire:
        return False
    if datetime.utcnow() > expire:
        _tokens.pop(token, None)
        return False
    return True


def logout_token(token: str) -> None:
    """登出（删除 Token）。"""
    _tokens.pop(token, None)
