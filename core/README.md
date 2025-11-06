# 核心模块 (Core Module)

## 概述

`core` 模块包含了智能体服务的核心组件，这些组件从原始的 `agent_server.py` 中重构而来，提供了模块化、可复用的功能。

## 模块结构

```
core/
├── __init__.py              # 模块初始化和导出
├── models.py               # 数据模型定义
├── conversation_manager.py # 会话管理
├── data_processor.py       # 数据处理
├── streaming_handler.py    # 流式响应处理
└── README.md              # 本文档
```

## 模块说明

### 1. models.py - 数据模型
定义了所有API请求和响应的数据模型，提供类型安全和数据验证。

**主要类**:
- `OpenAIMessage`: OpenAI消息格式
- `OpenAIRequest`: OpenAI兼容的请求格式
- `TrainData`: SQL训练数据模型
- `AgentResponse`: 智能体响应模型
- 各种响应模型 (`ErrorResponse`, `SuccessResponse` 等)

### 2. conversation_manager.py - 会话管理
管理多轮对话的会话状态和历史记录。

**核心功能**:
- 会话隔离（支持 conversation_id、user_id、session_id）
- 会话历史存储和检索
- 消息合并和管理
- 并发安全的会话操作

### 3. data_processor.py - 数据处理
处理各种特殊标记的数据查询和处理逻辑。

**核心功能**:
- 特殊标记检测 (`[power_knowledge]`, `[query_data]`, `[generate_report]`)
- 异步数据查询处理
- 对话上下文构建
- 输入文本处理和格式化

### 4. streaming_handler.py - 流式响应处理
处理流式响应的生成、心跳机制、事件处理。

**核心功能**:
- OpenAI兼容的流式响应格式
- 心跳机制防止连接超时
- 错误处理和状态管理
- 回调处理机制

## 使用方式

### 导入模块
```python
# 导入所有核心组件
from core import (
    conversation_manager,
    data_processor,
    StreamingResponseGenerator,
    OpenAIRequest
)

# 或者单独导入
from core.models import OpenAIRequest
from core.conversation_manager import conversation_manager
```

### 在路由中使用
```python
# 在 app/routers/agent_server_refactored.py 中
from core.models import OpenAIRequest
from core.conversation_manager import conversation_manager
from core.data_processor import data_processor
from core.streaming_handler import StreamingResponseGenerator
```

## 设计原则

1. **单一职责**: 每个模块都有明确的职责边界
2. **低耦合**: 模块间依赖关系清晰，避免循环引用
3. **高内聚**: 相关功能集中在同一模块中
4. **可扩展**: 支持功能扩展和定制
5. **类型安全**: 完整的类型提示和验证

## 依赖关系

```
models.py (基础数据模型)
    ↑
conversation_manager.py (依赖 models)
    ↑
data_processor.py (依赖 models)
    ↑
streaming_handler.py (独立模块)
    ↑
agent_server_refactored.py (使用所有模块)
```

## 注意事项

1. **导入路径**: 从路由模块导入时使用 `from core.xxx import xxx`
2. **模块位置**: 所有核心模块都位于项目根目录的 `core/` 文件夹中
3. **向后兼容**: 保持与原有API的完全兼容性
4. **生产环境**: 建议在生产环境中使用Redis替代内存存储

## 扩展指南

### 添加新的数据处理器
1. 在 `data_processor.py` 中添加新的处理方法
2. 在 `DataProcessor` 类中实现相应的逻辑
3. 更新 `detect_special_markers` 方法以识别新标记

### 添加新的数据模型
1. 在 `models.py` 中定义新的 Pydantic 模型
2. 在 `__init__.py` 中导出新模型
3. 在需要的地方导入和使用

### 扩展会话管理功能
1. 在 `ConversationManager` 类中添加新方法
2. 确保线程安全（使用 `async with self._lock`）
3. 更新相关的类型提示和文档