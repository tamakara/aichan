# AIChan

一个基于 `LangChain + LangGraph` 的模块化 AI 助手示例项目，采用 `uv workspace` 管理多包结构。  
当前采用 `Nexus` 中央队列的 Pull 架构：所有外部输入先入队，再由 Brain 统一消费。

## 项目文档

- 0号文档（边界说明）：[docs/0.boundary.md](docs/0.boundary.md)
- 1号文档（设计文档）：[docs/1.system-design.md](docs/1.system-design.md)
- 2号文档（架构文档）：[docs/2.project-structure.md](docs/2.project-structure.md)

## 架构概览

1. `plugins`：插件层（I/O 总线），统一承载输入渠道与动作工具能力。
2. `nexus`：中央神经枢纽，维护异步队列并驱动消费心跳。
3. `brain`：推理层，基于 LangGraph 执行“推理 -> 调用能力 -> 再推理”。
4. `memory`：记忆扩展层（当前占位），后续承载长期/外部记忆能力扩展。
5. `core`：共享基础层，提供配置、日志、接口契约与数据模型。

结构细节与关键文件映射见：[docs/2.project-structure.md](docs/2.project-structure.md)。  
系统设计意图与演进思路见：[docs/1.system-design.md](docs/1.system-design.md)。

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置模型参数

服务启动入口在 `main.py`（接口定义在 `cli_server.py`）。请按你的实际环境确认：

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL_NAME`
- `LLM_TEMPERATURE`

### 3. 启动服务端（内置 CLI 输入监听）

```bash
# 启动 AIChan 服务端
uv run python main.py
```

服务启动后可直接在当前终端输入消息，输入监听器会将内容推入 `Nexus` 队列。

## 目录结构

```text
.
├─ main.py
├─ cli_server.py
├─ cli_client.py
├─ pyproject.toml
├─ uv.lock
├─ docs
│  ├─ 0.boundary.md
│  ├─ 1.system-design.md
│  └─ 2.project-structure.md
└─ packages
   ├─ core
   ├─ plugins
   ├─ nexus
   ├─ brain
   └─ memory
```

## 常见自定义点

- 调整中枢队列与消费循环：`packages/nexus/src/nexus/hub.py`
- 替换推理流程：`packages/brain/src/brain/brain.py`
- 扩展记忆存取能力：`packages/memory/src/memory/`
- 扩展双工插件能力：`packages/plugins/src/plugins/channels/`、`packages/plugins/src/plugins/tools/`



