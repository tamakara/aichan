"""
CLI MCP Server 包入口。

该包实现了一个“HTTP 网关 + MCP 工具服务”的组合服务：
1. HTTP 侧负责消息读写与 SSE 推送；
2. MCP 侧负责向 Agent 暴露发送/拉取工具；
3. 两侧共享统一消息存储，实现人类输入与 Agent 行动闭环。
"""
