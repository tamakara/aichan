from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

"""
CLI 通道数据模型定义。

该模块只负责描述请求与响应的数据结构，不承载业务逻辑。
"""

# 通道身份枚举：当前只允许 AI 与用户两类消息来源。
CLIChannelIdentity = Literal["ai", "user"]


class SendMessageRequest(BaseModel):
    """`POST /v1/messages` 请求体模型。"""

    # 发送方身份：`user` 表示人类输入，`ai` 表示系统回写。
    sender: CLIChannelIdentity
    # 消息正文：至少 1 个字符，空白字符串会在存储层再次清洗。
    text: str = Field(..., min_length=1)


class ChatMessage(BaseModel):
    """通道内统一消息结构。"""

    # 自增消息 ID，用于增量拉取与 SSE 游标推进。
    id: int = Field(..., ge=1)
    # 消息发送方。
    sender: CLIChannelIdentity
    # 消息内容文本。
    text: str
    # 服务器生成的 UTC ISO8601 时间戳。
    created_at: str
