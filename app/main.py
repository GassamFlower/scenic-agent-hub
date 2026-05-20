"""
FastAPI 启动入口。

提供以下接口:
- GET  /health                        健康检查
- POST /api/v1/chat                   业务主入口（对话）
- GET  /api/v1/sessions               会话列表
- GET  /api/v1/sessions/{id}/history  会话历史
- GET  /api/v1/reviews                待审核列表
- POST /api/v1/reviews/{id}/complete  完成审核
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.memory import session_store
from app.core.review import review_queue
from app.core.auth import ADMIN_USERNAME, create_token, logout_token, verify_admin, verify_token
from app.core.knowledge_base import knowledge_base
from app.core.unanswered import unanswered_tracker
from app.core.scenic_config import scenic_config
from app.graph import app_graph

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
#  请求/响应模型
# ════════════════════════════════════════════════════════════


class ChatRequest(BaseModel):
    """统一请求模型：从小程序/网页/测试脚本进入的入参。"""

    user_id: str
    query: str
    authenticated: bool = False
    require_human_review: bool = False
    # 会话 ID（不传则自动生成，多轮对话需复用同一 session_id）
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    """统一响应模型。"""

    session_id: str
    response: str
    intent: str
    memory: List[Dict[str, str]]
    context: Dict[str, Any]
    review_id: Optional[str] = None
    error: Optional[str] = None


class ReviewAction(BaseModel):
    """审核操作请求体。"""

    approved: bool
    reviewer_note: str = ""


# ════════════════════════════════════════════════════════════
#  FastAPI 应用
# ════════════════════════════════════════════════════════════

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("未处理异常: %s %s -> %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误，请稍后重试"})


_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index():
    """访问根路径时返回测试界面。"""
    html_file = _STATIC_DIR / "index.html"
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Agent Hub is running</h1><p>Visit <a href='/docs'>/docs</a></p>")


@app.get("/health")
def health() -> Dict[str, str]:
    """健康检查接口。"""
    return {"status": "ok", "env": settings.app_env}


@app.post(f"{settings.api_prefix}/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    """
    业务主入口:
    1) 生成或复用 session_id
    2) 从 SessionStore 加载历史记忆
    3) 构造 AgentState 并执行 LangGraph 工作流
    4) 将更新后的记忆保存回 SessionStore
    5) 返回响应
    """
    sid = payload.session_id or f"s-{uuid4().hex[:12]}"

    # 从持久化存储加载历史记忆
    memory = session_store.get_memory(sid)

    state = {
        "session_id": sid,
        "user_id": payload.user_id,
        "query": payload.query,
        "authenticated": payload.authenticated,
        "require_human_review": payload.require_human_review,
        "memory": memory,
        "context": {},
        "metadata": payload.metadata,
    }

    result = app_graph.invoke(state)

    # 持久化更新后的记忆
    updated_memory = result.get("memory", [])
    session_store.save_memory(sid, payload.user_id, updated_memory)

    return ChatResponse(
        session_id=sid,
        response=result.get("final_response", ""),
        intent=result.get("intent", "unknown"),
        memory=updated_memory,
        context=result.get("context", {}),
        review_id=result.get("review_id"),
        error=result.get("error"),
    )


# ════════════════════════════════════════════════════════════
#  会话管理接口
# ════════════════════════════════════════════════════════════


@app.get(f"{settings.api_prefix}/sessions")
def list_sessions(limit: int = 20) -> List[Dict[str, Any]]:
    """列出最近的会话。"""
    return session_store.list_sessions(limit=limit)


@app.get(f"{settings.api_prefix}/sessions/{{session_id}}/history")
def get_session_history(session_id: str) -> Dict[str, Any]:
    """获取指定会话的对话历史。"""
    memory = session_store.get_memory(session_id)
    return {"session_id": session_id, "memory": memory, "turn_count": len(memory) // 2}


# ════════════════════════════════════════════════════════════
#  人工审核接口
# ════════════════════════════════════════════════════════════


@app.get(f"{settings.api_prefix}/reviews")
def list_reviews(limit: int = 50) -> List[Dict[str, Any]]:
    """列出待审核项。"""
    return review_queue.list_pending(limit=limit)


@app.get(f"{settings.api_prefix}/reviews/{{review_id}}")
def get_review(review_id: str) -> Dict[str, Any]:
    """获取单条审核记录。"""
    item = review_queue.get(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="审核记录不存在")
    return item


@app.post(f"{settings.api_prefix}/reviews/{{review_id}}/complete")
def complete_review(review_id: str, action: ReviewAction) -> Dict[str, str]:
    """完成人工审核。"""
    success = review_queue.complete(
        review_id=review_id,
        approved=action.approved,
        reviewer_note=action.reviewer_note,
    )
    if not success:
        raise HTTPException(status_code=400, detail="审核记录不存在或已处理")
    status = "approved" if action.approved else "rejected"
    return {"review_id": review_id, "status": status, "message": "审核完成"}


# ════════════════════════════════════════════════════════════
#  管理后台 API
# ════════════════════════════════════════════════════════════


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    success: bool
    token: str = ""
    message: str = ""


class KbItem(BaseModel):
    keywords: str
    question: str
    answer: str
    category: str = "通用"


class KbUpdate(BaseModel):
    keywords: Optional[str] = None
    question: Optional[str] = None
    answer: Optional[str] = None
    category: Optional[str] = None
    enabled: Optional[int] = None


@app.post(f"{settings.api_prefix}/admin/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest):
    """管理后台登录。"""
    if verify_admin(payload.username, payload.password):
        token = create_token()
        return AdminLoginResponse(success=True, token=token, message="登录成功")
    return AdminLoginResponse(success=False, message="用户名或密码错误")


@app.post(f"{settings.api_prefix}/admin/verify")
def admin_verify(request: Request):
    """校验管理后台 Token 是否有效。"""
    token = request.headers.get("X-Admin-Token", "")
    return {"valid": verify_token(token)}


def _require_admin(request: Request):
    """中间件：校验管理后台请求的 Token。"""
    token = request.headers.get("X-Admin-Token", "")
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="未登录或登录已过期")


# ── 知识库管理 ──────────────────────────────────────────────


@app.get(f"{settings.api_prefix}/admin/knowledge")
def list_knowledge(request: Request, enabled_only: bool = False):
    """列出知识库所有条目。"""
    _require_admin(request)
    return knowledge_base.list_all(enabled_only=enabled_only)


@app.get(f"{settings.api_prefix}/admin/knowledge/{{item_id}}")
def get_knowledge(request: Request, item_id: int):
    """获取单条知识库条目。"""
    _require_admin(request)
    item = knowledge_base.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="条目不存在")
    return item


@app.post(f"{settings.api_prefix}/admin/knowledge")
def add_knowledge(request: Request, item: KbItem):
    """新增知识库条目。"""
    _require_admin(request)
    item_id = knowledge_base.add(
        keywords=item.keywords,
        question=item.question,
        answer=item.answer,
        category=item.category,
    )
    return {"id": item_id, "message": "添加成功"}


@app.put(f"{settings.api_prefix}/admin/knowledge/{{item_id}}")
def update_knowledge(request: Request, item_id: int, update: KbUpdate):
    """更新知识库条目。"""
    _require_admin(request)
    kwargs = {k: v for k, v in update.model_dump(exclude_none=True).items() if v is not None}
    if knowledge_base.update(item_id, **kwargs):
        return {"message": "更新成功"}
    raise HTTPException(status_code=404, detail="条目不存在")


@app.delete(f"{settings.api_prefix}/admin/knowledge/{{item_id}}")
def delete_knowledge(request: Request, item_id: int):
    """删除知识库条目。"""
    _require_admin(request)
    if knowledge_base.delete(item_id):
        return {"message": "删除成功"}
    raise HTTPException(status_code=404, detail="条目不存在")


# ── 未命中问题管理 ──────────────────────────────────────────


@app.get(f"{settings.api_prefix}/admin/unanswered")
def list_unanswered(request: Request, limit: int = 100):
    """列出待处理的未命中问题。"""
    _require_admin(request)
    return unanswered_tracker.list_pending(limit=limit)


@app.post(f"{settings.api_prefix}/admin/unanswered/{{item_id}}/resolve")
def resolve_unanswered(request: Request, item_id: int):
    """标记未命中问题为已处理。"""
    _require_admin(request)
    if unanswered_tracker.mark_resolved(item_id):
        return {"message": "已标记为已处理"}
    raise HTTPException(status_code=404, detail="记录不存在")


@app.post(f"{settings.api_prefix}/admin/unanswered/{{item_id}}/to-faq")
def unanswered_to_faq(request: Request, item_id: int):
    """将未命中问题一键转为知识库条目。"""
    _require_admin(request)
    item = unanswered_tracker.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    # 自动提取关键词（取问题中前 10 个字）
    query = item.get("query", "")
    keywords = query[:10] if len(query) > 10 else query
    item_id_new = knowledge_base.add(
        keywords=keywords,
        question=query,
        answer=f"关于「{query}」的问题，请在这里补充标准答案。",
        category="待补充",
    )
    unanswered_tracker.mark_resolved(item_id)
    return {"id": item_id_new, "message": "已转为知识库条目，请编辑补充标准答案"}


# ── 热门问题统计 ──────────────────────────────────────────────


@app.get(f"{settings.api_prefix}/admin/hot-questions")
def hot_questions(request: Request, limit: int = 10):
    """获取热门问题 Top N。"""
    _require_admin(request)
    items = knowledge_base.list_all(enabled_only=True)
    items.sort(key=lambda x: x.get("hit_count", 0), reverse=True)
    return items[:limit]


# ── 景区配置管理 ──────────────────────────────────────────────


class ScenicConfigItem(BaseModel):
    key: str
    value: str


@app.get(f"{settings.api_prefix}/admin/scenic-config")
def get_scenic_config(request: Request):
    """获取所有景区配置。"""
    _require_admin(request)
    return scenic_config.get_all_with_labels()


@app.put(f"{settings.api_prefix}/admin/scenic-config")
def update_scenic_config(request: Request, items: List[ScenicConfigItem]):
    """批量更新景区配置。"""
    _require_admin(request)
    updates = {item.key: item.value for item in items}
    count = scenic_config.set_batch(updates)
    return {"message": f"已更新 {count} 项配置"}


# ── 管理后台静态页面 ────────────────────────────────────────


_ADMIN_DIR = Path(__file__).resolve().parent.parent / "static" / "admin"
_WIDGET_DIR = Path(__file__).resolve().parent.parent / "static" / "widget"


@app.get("/admin/{page_name}", response_class=HTMLResponse, include_in_schema=False)
def admin_page(page_name: str):
    """提供管理后台静态页面。"""
    html_file = _ADMIN_DIR / page_name
    try:
        html_file = html_file.resolve()
        if not str(html_file).startswith(str(_ADMIN_DIR.resolve())):
            raise HTTPException(status_code=404, detail="页面不存在")
    except (ValueError, OSError):
        raise HTTPException(status_code=404, detail="页面不存在")
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="页面不存在")


@app.get("/widget/{page_name}", response_class=HTMLResponse, include_in_schema=False)
def widget_page(page_name: str):
    """提供嵌入式对话组件页面。"""
    html_file = _WIDGET_DIR / page_name
    try:
        html_file = html_file.resolve()
        if not str(html_file).startswith(str(_WIDGET_DIR.resolve())):
            raise HTTPException(status_code=404, detail="页面不存在")
    except (ValueError, OSError):
        raise HTTPException(status_code=404, detail="页面不存在")
    if html_file.exists():
        return HTMLResponse(content=html_file.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="页面不存在")
