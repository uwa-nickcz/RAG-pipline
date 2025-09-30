# RAG Pipeline 系统重构指南

## 重构概述

本次重构对 RAG Pipeline 系统进行了全面的模块化改造，重点优化了流式接口实现和心跳机制，提升了代码的可维护性和稳定性。

## 新的目录结构

```
app/
├── __init__.py
├── main.py                    # 主应用入口（已重构）
├── qa.py                      # 问答模块（已优化）
├── contract_parse.py          # 合同解析模块（已优化）
├── core/                      # 核心功能模块（新增）
│   ├── __init__.py
│   ├── events.py             # 事件管理
│   ├── streaming.py          # 流式响应管理
│   ├── callbacks.py          # 回调处理器
│   └── heartbeat.py          # 心跳检测机制
├── services/                  # 服务层（新增）
│   ├── __init__.py
│   ├── agent_service.py      # 智能体服务
│   └── streaming_service.py  # 流式服务
├── utils/                     # 工具模块（新增）
│   ├── __init__.py
│   ├── helpers.py            # 辅助函数
│   ├── validators.py         # 验证器
│   └── formatters.py         # 格式化器
└── routers/                   # 路由模块
    ├── __init__.py
    ├── agent_server.py       # 智能体路由（已重构）
    ├── agent_server_legacy.py # 原版本备份
    ├── asr_server.py
    ├── file_server.py
    ├── pgsql_server.py
    └── tts_server.py
```

## 主要改进

### 1. 模块化设计

- **核心模块 (core/)**：包含系统核心功能组件
- **服务层 (services/)**：封装业务逻辑
- **工具模块 (utils/)**：提供通用工具函数
- **路由层 (routers/)**：处理HTTP请求

### 2. 流式接口优化

#### 新的流式响应管理器
```python
from app.core.streaming import StreamingResponseManager, HeartbeatConfig
from app.services.streaming_service import StreamingService

# 配置心跳参数
heartbeat_config = HeartbeatConfig(
    interval=15.0,           # 心跳间隔
    timeout_threshold=300,   # 超时阈值
    progress_interval=30.0   # 进度提示间隔
)

# 创建流式服务
streaming_service = StreamingService(heartbeat_config)
```

#### 统一的事件处理
```python
from app.core.events import EventGenerator, EventType

# 生成标准化的SSE事件
event_generator = EventGenerator(request_id, model)
token_event = event_generator.generate_token_event(content)
heartbeat_event = event_generator.generate_heartbeat_event()
```

### 3. 心跳机制增强

#### 全局心跳管理器
```python
from app.core.heartbeat import global_heartbeat_manager

# 启动心跳监控
await global_heartbeat_manager.start()

# 注册连接
await global_heartbeat_manager.get_monitor().register_connection(
    connection_id="stream-123",
    metadata={"user": "test", "model": "gpt-3.5"},
    on_timeout=handle_timeout,
    on_error=handle_error
)
```

#### 连接状态监控
- 自动检测连接超时
- 错误计数和处理
- 连接统计信息
- 自动清理过期连接

### 4. 智能体服务重构

#### 服务层封装
```python
from app.services.agent_service import AgentService

agent_service = AgentService()

# 执行智能体任务
result = await agent_service.execute_agent(
    input_text="用户问题",
    executor_type="metahuman",
    max_iterations=5
)
```

#### 流式执行
```python
# 创建流式响应
response = await streaming_service.create_monitored_stream_response(
    input_text=input_text,
    model=model,
    executor_type="metahuman",
    max_iterations=5
)
```

## 使用指南

### 1. 启动系统

```bash
cd /d:/workspace/数字人/frontend/ai/app/digitalHuman/server/api/rag_pipline
python app/main.py
```

### 2. API接口

#### 非流式智能体查询
```http
POST /agent/v1/chat/completions/no_steam
Content-Type: application/json

{
    "model": "Qwen3-30B-A3B-FP8",
    "messages": [
        {"role": "user", "content": "你好"}
    ],
    "max_iterations": 5
}
```

#### 流式智能体查询
```http
POST /agent/v1/chat/completions
Content-Type: application/json

{
    "model": "Qwen3-30B-A3B-FP8",
    "messages": [
        {"role": "user", "content": "你好"}
    ],
    "max_iterations": 5
}
```

#### 服务状态查询
```http
GET /agent/status
```

#### 心跳配置更新
```http
POST /agent/config/heartbeat
Content-Type: application/json

{
    "interval": 15.0,
    "timeout_threshold": 300,
    "progress_interval": 30.0
}
```

### 3. 自定义扩展

#### 添加新的执行器
```python
# 在 agent_service.py 中添加
class AgentService:
    def __init__(self):
        self.executors = {
            "web": agent_executor_web,
            "metahuman": agent_executor_for_metahuman,
            "v3": agent_executor_for_v3,
            "custom": your_custom_executor  # 新增
        }
```

#### 自定义回调处理器
```python
from app.core.callbacks import StreamingCallbackHandler

class CustomCallbackHandler(StreamingCallbackHandler):
    async def on_custom_event(self, event_data):
        # 处理自定义事件
        await self.queue.put({
            "type": "custom",
            "data": event_data
        })
```

## 配置说明

### 心跳配置参数

- `interval`: 心跳发送间隔（秒），默认15秒
- `timeout_threshold`: 连接超时阈值（次数），默认300次
- `progress_interval`: 进度提示间隔（秒），默认30秒

### 执行器类型

- `metahuman`: 数字人智能体执行器（默认）
- `web`: 网络搜索智能体执行器
- `v3`: V3版本智能体执行器

## 兼容性说明

### 向后兼容

- 原有的API接口保持不变
- 响应格式完全兼容OpenAI标准
- 现有客户端无需修改

### 迁移建议

1. **逐步迁移**：可以同时运行新旧版本
2. **测试验证**：在生产环境部署前充分测试
3. **监控观察**：关注心跳机制和连接状态
4. **性能对比**：对比新旧版本的性能指标

## 故障排除

### 常见问题

1. **导入错误**
   ```
   ModuleNotFoundError: No module named 'app.core'
   ```
   解决：确保Python路径正确，检查__init__.py文件

2. **心跳连接失败**
   ```
   HeartbeatMonitor connection timeout
   ```
   解决：检查网络连接，调整心跳配置参数

3. **流式响应中断**
   ```
   StreamingResponse connection closed
   ```
   解决：检查客户端连接，增加重试机制

### 调试模式

启用详细日志：
```python
import logging
logging.getLogger('rag_pipeline').setLevel(logging.DEBUG)
```

查看连接统计：
```python
stats = global_heartbeat_manager.get_monitor().get_connection_stats()
print(stats)
```

## 性能优化建议

1. **连接池管理**：合理设置连接池大小
2. **心跳频率**：根据网络环境调整心跳间隔
3. **内存使用**：定期清理过期连接
4. **并发控制**：限制同时处理的流式请求数量

## 未来规划

1. **监控面板**：添加Web界面监控系统状态
2. **负载均衡**：支持多实例部署
3. **缓存机制**：添加智能缓存提升性能
4. **插件系统**：支持动态加载扩展模块