"""
重构后的智能体服务路由模块

该模块提供了完整的智能体服务API，包括多轮对话、会话管理、
流式响应等功能。通过模块化设计提高了代码的可维护性和可扩展性。

Author: AI Assistant
Date: 2024
"""

import json
import time
from typing import Dict
from dotenv import load_dotenv
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

# 导入自定义模块
from core.models import (
    OpenAIRequest, TrainData, ToolStep, AgentResponse,
    ConversationClearRequest, ConversationHistoryResponse,
    ErrorResponse, SuccessResponse
)
from core.conversation_manager import conversation_manager
from core.data_processor import data_processor
from core.streaming_handler import StreamingResponseGenerator, HeartbeatManager

# 导入外部依赖
from agents.agent import agent_executor_web, agent_executor_for_metahuman, chain
from tools import sql_train

# 加载环境变量
load_dotenv()

# 创建路由器
router = APIRouter(prefix="/agent", tags=["agent后端"])

# 创建全局组件实例
streaming_generator = StreamingResponseGenerator("Qwen3-30B-A3B-FP8")


@router.post("/train", response_model=Dict)
async def train_sql(request: TrainData):
    """训练SQL模型
    
    Args:
        request: 训练数据请求
        
    Returns:
        Dict: 训练结果
    """
    try:
        sql_train(
            question=request.question,
            ddl=request.ddl,
            documentation=request.documentation,
            sql=request.sql
        )
        return {"code": 200}
    except Exception as e:
        return {"error": str(e)}


@router.post("/v1/chat/completions/no_steam")
async def run_agent(request: OpenAIRequest):
    """执行智能体查询（非流式）
    
    Args:
        request: OpenAI格式的请求
        
    Returns:
        Dict: OpenAI兼容的响应格式
    """
    start_time = time.time()
    user_messages = [msg for msg in request.messages if msg.role == "user"]
    if not user_messages:
        return {"error": "No user message found"}

    input_text = user_messages[-1].content
    max_iterations = request.max_iterations or 5

    # 执行智能体
    result = await agent_executor_for_metahuman.ainvoke(
        {"input": input_text},
        config={"max_iterations": max_iterations}
    )

    # 整理执行步骤
    steps = []
    for step in result.get("intermediate_steps", []):
        tool_call = step[0]
        tool_output = step[1]

        steps.append(ToolStep(
            action=tool_call.tool,
            input=tool_call.tool_input,
            output=tool_output
        ))

    execution_time = time.time() - start_time

    # 返回OpenAI兼容格式
    return {
        "id": f"chatcmpl-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": result["output"]
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": len(input_text),
            "completion_tokens": len(result["output"]),
            "total_tokens": len(input_text) + len(result["output"])
        },
        "agent_details": {
            "input": input_text,
            "steps": [step.dict() for step in steps],
            "execution_time": execution_time
        }
    }


@router.post("/v3/chat/completions")
async def stream_chat_completion(request: OpenAIRequest):
    """流式执行LLM查询 - OpenAI兼容格式，支持多轮对话和会话隔离
    
    Args:
        request: OpenAI格式的请求
        
    Returns:
        StreamingResponse: 流式响应
    """
    if not request.messages:
        return streaming_generator.create_streaming_response(
            streaming_generator.generate_error_response("No messages found")
        )

    # 获取会话标识符和合并消息
    conversation_key = await conversation_manager.get_conversation_key(request)
    all_messages = await conversation_manager.merge_messages(request)

    # 构建对话上下文
    conversation_context, current_user_input = data_processor.build_context_string(all_messages)
    input_text,tag = data_processor.build_input_text(all_messages, conversation_context, current_user_input)
    # 生成唯一的ID
    request_id = f"chatcmpl-{int(time.time())}"
    created_time = int(time.time())

    async def event_generator():
        """生成服务器发送事件 - 带心跳机制"""
        
        # 创建心跳管理器
        heartbeat_manager = HeartbeatManager(30)
        
        # 发送初始响应
        yield await streaming_generator.generate_initial_response(request_id, created_time)

        # 第一步：基于历史对话生成新问题
        is_multi_turn = len([msg for msg in all_messages if msg.role in ["user", "assistant"]]) > 1
        
        if is_multi_turn:
            # 多轮对话：先生成新问题
            question_prompt = await data_processor.generate_question_from_history(all_messages)
            
            # 使用大模型生成新问题
            generated_question = ""
            try:
                async for chunk in chain.astream({"input": question_prompt}):
                    if content := chunk.content:
                        generated_question += content
                
                # 使用生成的问题作为检查输入（去除 <think>...</think> 和多余空白）
                check_input = generated_question
                # 移除 <think>...</think> 内容（包含其中的思考文本）
                while True:
                    lower = check_input.lower()
                    s_idx = lower.find("<think>")
                    e_idx = lower.find("</think>")
                    if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
                        check_input = check_input[:s_idx] + check_input[e_idx + len("</think>"):]
                    else:
                        break
                # 压缩换行、制表符等空白为单个空格
                check_input = " ".join(check_input.split()).strip() + '['+tag+']'
                print(f"生成的问题: {check_input}")
            except Exception as e:
                # 如果生成问题失败，使用原始用户输入（并清理无关字符）
                check_input = all_messages[-1].content
                # 清理可能存在的 <think>...</think> 与空白
                while True:
                    lower = check_input.lower()
                    s_idx = lower.find("<think>")
                    e_idx = lower.find("</think>")
                    if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
                        check_input = check_input[:s_idx] + check_input[e_idx + len("</think>"):]
                    else:
                        break
                check_input = " ".join(check_input.split()).strip()
                print(f"问题生成失败，使用原始输入: {e}")
        else:
            # 单轮对话：直接使用用户输入（并清理无关字符）
            check_input = all_messages[-1].content
            # 清理可能存在的 <think>...</think> 与空白
            while True:
                lower = check_input.lower()
                s_idx = lower.find("<think>")
                e_idx = lower.find("</think>")
                if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
                    check_input = check_input[:s_idx] + check_input[e_idx + len("</think>"):]
                else:
                    break
            check_input = " ".join(check_input.split()).strip()

        # 第二步：基于生成的问题进行数据处理和查询
        processed_input = input_text
        
        # 检测特殊标记
        processing_type = data_processor.detect_special_markers(check_input)
        
        try:
            if processing_type == "power_knowledge":
                result = await data_processor.process_power_knowledge(check_input)
                processed_input = data_processor.build_processed_input(
                    processing_type, result, input_text, check_input, all_messages, is_multi_turn
                )
            
            elif processing_type == "query_data":
                # 发送处理提示
                yield await streaming_generator.generate_processing_hint(request_id, created_time)
                
                result = await data_processor.process_query_data(check_input)
                processed_input = data_processor.build_processed_input(
                    processing_type, result, input_text, check_input, all_messages, is_multi_turn
                )
            
            elif processing_type == "generate_report":
                # 发送处理提示
                yield await streaming_generator.generate_processing_hint(request_id, created_time)
                
                result = await data_processor.process_generate_report(check_input)
                processed_input = data_processor.build_processed_input(
                    processing_type, result, input_text, check_input, all_messages, is_multi_turn
                )
            
            else:
                # 没有特殊标记，使用默认处理
                sql_result, knowledge_result = await data_processor.process_default_query(check_input)
                processed_input = data_processor.build_default_processed_input(
                    sql_result, knowledge_result, input_text, check_input, is_multi_turn
                )
        
        except Exception as e:
            # 异常处理
            sql_result, knowledge_result = await data_processor.process_default_query(check_input)
            processed_input = data_processor.build_default_processed_input(
                sql_result, knowledge_result, input_text, check_input, is_multi_turn
            )
            print(f"数据库错误：{e}")

        # 重置心跳时间
        heartbeat_manager.reset()
        print(processed_input)

        try:
            # 第三步：将处理后的输入发送给大模型获取最终回答
            response_content = ""
            async for chunk in chain.astream({"input": processed_input}):
                if content := chunk.content:
                    response_content += content  # 收集响应内容
                    yield await streaming_generator.generate_content_chunk(request_id, created_time, content)

                # 检查并发送心跳
                if heartbeat_manager.should_send_heartbeat():
                    yield await streaming_generator.generate_heartbeat(request_id, created_time)
                    heartbeat_manager.update_heartbeat_time()

        except Exception as e:
            error_data = streaming_generator.create_error_data(request_id, created_time, f"Error: {str(e)}")
            yield f"data: {json.dumps(error_data)}\n\n"

        # 保存助手响应到会话历史
        await conversation_manager.save_assistant_response(conversation_key, response_content)

        # 发送结束标记
        yield await streaming_generator.generate_finish_response(request_id, created_time)

    return streaming_generator.create_streaming_response(event_generator())


@router.post("/v3/conversation/clear", response_model=SuccessResponse)
async def clear_conversation(request: ConversationClearRequest):
    """清空指定会话历史
    
    Args:
        request: 清空会话请求
        
    Returns:
        SuccessResponse: 成功响应
    """
    # 构建会话key
    conversation_key = "default_conversation"
    if request.conversation_id:
        conversation_key = f"conv_{request.conversation_id}"
    elif request.session_id:
        conversation_key = f"session_{request.session_id}"
    elif request.user_id:
        conversation_key = f"user_{request.user_id}_default"
    
    await conversation_manager.clear_conversation_history(conversation_key)
    return SuccessResponse(message="会话历史已清空")


@router.get("/v3/conversation/history", response_model=ConversationHistoryResponse)
async def get_conversation_history_api(
    conversation_id: str = None, 
    session_id: str = None, 
    user_id: str = None
):
    """获取指定会话历史
    
    Args:
        conversation_id: 会话ID
        session_id: 会话ID
        user_id: 用户ID
        
    Returns:
        ConversationHistoryResponse: 会话历史响应
    """
    # 构建会话key
    conversation_key = "default_conversation"
    if conversation_id:
        conversation_key = f"conv_{conversation_id}"
    elif session_id:
        conversation_key = f"session_{session_id}"
    elif user_id:
        conversation_key = f"user_{user_id}_default"
    
    history = await conversation_manager.get_conversation_history(conversation_key)
    return ConversationHistoryResponse(
        code=200,
        data={
            "conversation_key": conversation_key,
            "messages": [{"role": msg.role, "content": msg.content} for msg in history]
        }
    )


@router.get("/v3/conversation/stats")
async def get_conversation_stats():
    """获取会话统计信息
    
    Returns:
        Dict: 会话统计信息
    """
    stats = conversation_manager.get_conversation_stats()
    return {
        "code": 200,
        "data": stats
    }


# ========== 可选：方便独立运行调试 ==========
if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(
        title="Agent API Service",
        description="重构后的智能体API服务",
        version="2.0.0"
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应该指定具体域名
        allow_credentials=True,
        allow_methods=["*"],  # 允许所有方法，包括 OPTIONS
        allow_headers=["*"],  # 允许所有头
    )
    # 将当前 router 挂载到 app 上
    app.include_router(router)

    uvicorn.run(app, host="192.168.112.228", port=8000)