"""
Conversation Service - 对话历史管理服务

提供：
1. 对话创建和管理
2. 消息历史存储
3. 上下文窗口管理
"""
from __future__ import annotations

import uuid
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from app.services.db import get_conn


@dataclass
class Message:
    """对话消息"""
    role: str  # 'user' | 'assistant' | 'system'
    content: str
    thinking: Optional[str] = None
    citations: Optional[List[Dict[str, Any]]] = None
    timestamp: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "thinking": self.thinking,
            "citations": self.citations,
            "timestamp": self.timestamp or datetime.utcnow().isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            thinking=data.get("thinking"),
            citations=data.get("citations"),
            timestamp=data.get("timestamp"),
        )


@dataclass
class Conversation:
    """对话"""
    id: str
    repo_id: str
    title: Optional[str] = None
    messages: List[Message] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "repo_id": self.repo_id,
            "title": self.title,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _ensure_table():
    """确保对话表存在"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            repo_id TEXT NOT NULL,
            title TEXT,
            messages TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversations_repo 
        ON conversations(repo_id)
    """)
    conn.commit()


def create_conversation(repo_id: str, title: Optional[str] = None) -> Conversation:
    """
    创建新对话
    """
    _ensure_table()
    conv_id = f"conv_{uuid.uuid4().hex[:12]}"
    now = datetime.utcnow().isoformat()
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO conversations (id, repo_id, title, messages, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (conv_id, repo_id, title, "[]", now, now)
    )
    conn.commit()
    
    return Conversation(
        id=conv_id,
        repo_id=repo_id,
        title=title,
        messages=[],
        created_at=now,
        updated_at=now,
    )


def get_conversation(conversation_id: str) -> Optional[Conversation]:
    """
    获取对话
    """
    _ensure_table()
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, repo_id, title, messages, created_at, updated_at FROM conversations WHERE id = ?",
        (conversation_id,)
    )
    row = cursor.fetchone()
    if not row:
        return None
    
    messages_data = json.loads(row[3]) if row[3] else []
    messages = [Message.from_dict(m) for m in messages_data]
    
    return Conversation(
        id=row[0],
        repo_id=row[1],
        title=row[2],
        messages=messages,
        created_at=row[4],
        updated_at=row[5],
    )


def list_conversations(repo_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    列出仓库的所有对话（不包含完整消息内容）
    """
    _ensure_table()
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, repo_id, title, messages, created_at, updated_at 
        FROM conversations 
        WHERE repo_id = ?
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (repo_id, limit)
    )
    rows = cursor.fetchall()
    
    result = []
    for row in rows:
        messages_data = json.loads(row[3]) if row[3] else []
        message_count = len(messages_data)
        # 获取最后一条用户消息作为预览
        last_user_msg = ""
        for m in reversed(messages_data):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")[:100]
                break
        
        result.append({
            "id": row[0],
            "repo_id": row[1],
            "title": row[2] or last_user_msg or "新对话",
            "message_count": message_count,
            "preview": last_user_msg,
            "created_at": row[4],
            "updated_at": row[5],
        })
    
    return result


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    thinking: Optional[str] = None,
    citations: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Message]:
    """
    添加消息到对话
    """
    conv = get_conversation(conversation_id)
    if not conv:
        return None
    
    msg = Message(
        role=role,
        content=content,
        thinking=thinking,
        citations=citations,
        timestamp=datetime.utcnow().isoformat(),
    )
    
    conv.messages.append(msg)
    now = datetime.utcnow().isoformat()
    
    # 自动生成标题（第一条用户消息）
    title = conv.title
    if not title and role == "user":
        title = content[:50] + ("..." if len(content) > 50 else "")
    
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE conversations 
        SET messages = ?, updated_at = ?, title = ?
        WHERE id = ?
        """,
        (json.dumps([m.to_dict() for m in conv.messages], ensure_ascii=False), now, title, conversation_id)
    )
    conn.commit()
    
    return msg


def delete_conversation(conversation_id: str) -> bool:
    """
    删除对话
    """
    _ensure_table()
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    return cursor.rowcount > 0


def clear_conversation(conversation_id: str) -> bool:
    """
    清空对话消息（保留对话记录）
    """
    conv = get_conversation(conversation_id)
    if not conv:
        return False
    
    now = datetime.utcnow().isoformat()
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE conversations SET messages = ?, updated_at = ? WHERE id = ?",
        ("[]", now, conversation_id)
    )
    conn.commit()
    return True


def get_context_messages(
    conversation_id: str,
    max_messages: int = 10,
    max_tokens: int = 4000,
) -> List[Dict[str, str]]:
    """
    获取用于 LLM 上下文的消息历史
    
    策略：
    1. 保留最近的 N 条消息
    2. 限制总 token 数
    3. 不包含 thinking 和 citations
    """
    conv = get_conversation(conversation_id)
    if not conv or not conv.messages:
        return []
    
    # 取最近的消息
    recent_messages = conv.messages[-max_messages:]
    
    # 估算 token 并裁剪
    result = []
    total_tokens = 0
    
    for msg in reversed(recent_messages):
        msg_tokens = len(msg.content) // 4
        if total_tokens + msg_tokens > max_tokens:
            break
        result.insert(0, {"role": msg.role, "content": msg.content})
        total_tokens += msg_tokens
    
    return result
