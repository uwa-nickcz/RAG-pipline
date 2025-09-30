# -*- coding: utf-8 -*-
"""
智能体服务模块 - 提供智能体执行的业务逻辑
"""
import time
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from agents.agent import (
    agent_executor_web,
    agent_executor_for_metahuman,
    agent_executor_for_v3
)
from logger import logger


@dataclass
class ToolStep:
    """工具执行步骤"""
    action: str
    input: Dict[str, Any]
    output: str
    execution_time: Optional[float] = None


@dataclass
class AgentExecutionResult:
    """智能体执行结果"""
    input: str
    output: str
    steps: List[ToolStep]
    execution_time: float
    success: bool
    error_message: Optional[str] = None


class AgentService:
    """智能体服务 - 封装智能体执行逻辑"""
    
    def __init__(self):
        """初始化智能体服务"""
        self.executors = {
            "web": agent_executor_web,
            "metahuman": agent_executor_for_metahuman,
            "v3": agent_executor_for_v3
        }
    
    async def execute_agent(
        self,
        input_text: str,
        executor_type: str = "metahuman",
        max_iterations: int = 5,
        callbacks: Optional[List] = None
    ) -> AgentExecutionResult:
        """
        执行智能体任务
        
        Args:
            input_text: 输入文本
            executor_type: 执行器类型 (web, metahuman, v3)
            max_iterations: 最大迭代次数
            callbacks: 回调处理器列表
            
        Returns:
            智能体执行结果
        """
        start_time = time.time()
        
        try:
            # 获取执行器
            executor = self.executors.get(executor_type)
            if not executor:
                raise ValueError(f"不支持的执行器类型: {executor_type}")
            
            # 构建执行配置
            config = {"max_iterations": max_iterations}
            if callbacks:
                config["callbacks"] = callbacks
            
            # 执行智能体
            logger.info(f"开始执行智能体任务，类型: {executor_type}")
            result = await executor.ainvoke(
                {"input": input_text},
                config=config
            )
            
            # 处理执行步骤
            steps = self._process_intermediate_steps(result.get("intermediate_steps", []))
            
            execution_time = time.time() - start_time
            logger.info(f"智能体任务执行完成，耗时: {execution_time:.2f}秒")
            
            return AgentExecutionResult(
                input=input_text,
                output=result["output"],
                steps=steps,
                execution_time=execution_time,
                success=True
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_message = f"智能体执行失败: {str(e)}"
            logger.error(error_message)
            
            return AgentExecutionResult(
                input=input_text,
                output="",
                steps=[],
                execution_time=execution_time,
                success=False,
                error_message=error_message
            )
    
    async def execute_agent_streaming(
        self,
        input_text: str,
        queue: asyncio.Queue,
        executor_type: str = "metahuman",
        max_iterations: int = 5,
        callbacks: Optional[List] = None
    ) -> asyncio.Task:
        """
        流式执行智能体任务
        
        Args:
            input_text: 输入文本
            queue: 事件队列
            executor_type: 执行器类型
            max_iterations: 最大迭代次数
            callbacks: 回调处理器列表
            
        Returns:
            异步任务对象
        """
        executor = self.executors.get(executor_type)
        if not executor:
            raise ValueError(f"不支持的执行器类型: {executor_type}")
        
        # 构建执行配置
        config = {"max_iterations": max_iterations}
        if callbacks:
            config["callbacks"] = callbacks
        
        # 创建并返回异步任务
        task = asyncio.create_task(
            executor.ainvoke(
                {"input": input_text},
                config=config
            )
        )
        
        logger.info(f"开始流式执行智能体任务，类型: {executor_type}")
        return task
    
    def _process_intermediate_steps(self, intermediate_steps: List) -> List[ToolStep]:
        """
        处理中间执行步骤
        
        Args:
            intermediate_steps: 原始中间步骤
            
        Returns:
            处理后的工具步骤列表
        """
        steps = []
        
        for step in intermediate_steps:
            if len(step) >= 2:
                tool_call = step[0]
                tool_output = step[1]
                
                steps.append(ToolStep(
                    action=getattr(tool_call, 'tool', 'unknown'),
                    input=getattr(tool_call, 'tool_input', {}),
                    output=str(tool_output)
                ))
        
        return steps
    
    def get_available_executors(self) -> List[str]:
        """
        获取可用的执行器类型
        
        Returns:
            执行器类型列表
        """
        return list(self.executors.keys())
    
    def validate_executor_type(self, executor_type: str) -> bool:
        """
        验证执行器类型是否有效
        
        Args:
            executor_type: 执行器类型
            
        Returns:
            是否有效
        """
        return executor_type in self.executors