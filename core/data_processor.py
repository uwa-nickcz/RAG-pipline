"""
数据处理模块

该模块负责处理各种特殊标记的数据查询和处理逻辑，
包括知识库查询、SQL查询、报告生成等功能。

Author: AI Assistant
Date: 2024
"""

import asyncio
from typing import Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor
from .models import OpenAIMessage
from tools import sqlsearch, databasesearch, generate_report
from prompt import AGENT_PROMPT_V3
import re


class DataProcessor:
    """数据处理器
    
    负责处理各种特殊标记和数据查询任务，支持异步执行和并发控制。
    """
    
    def __init__(self):
        """初始化数据处理器"""
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.plotly_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="plotly_worker")
    
    def detect_special_markers(self, text: str) -> Optional[str]:
        """检测文本中的特殊标记
        
        Args:
            text: 要检测的文本
            
        Returns:
            Optional[str]: 检测到的特殊标记类型，如果没有则返回None
        """
        text_lower = text.lower()
        
        if '[power_knowledge]' in text_lower:
            return "power_knowledge"
        elif '[query_data]' in text_lower:
            return "query_data"
        elif '[generate_report]' in text_lower:
            return "generate_report"
        else:
            return None
    
    async def process_power_knowledge(self, text: str) -> str:
        """处理知识库查询
        
        Args:
            text: 包含特殊标记的文本
            
        Returns:
            str: 查询结果
        """
        clean_text = text.replace('[power_knowledge]', '')
        result = await asyncio.get_event_loop().run_in_executor(
            self.executor,
            lambda: databasesearch(clean_text)
        )
        return result
    
    async def process_query_data(self, text: str) -> str:
        """处理数据查询
        
        Args:
            text: 包含特殊标记的文本
            
        Returns:
            str: 查询结果
        """
        clean_text = text.replace('[query_data]', '')
        result = await asyncio.get_event_loop().run_in_executor(
            self.executor,
            lambda: sqlsearch(clean_text)
        )
        return result
    
    async def process_generate_report(self, text: str) -> str:
        """处理报告生成
        
        Args:
            text: 包含特殊标记的文本
            
        Returns:
            str: 生成结果
        """
        clean_text = text.replace('[generate_report]', '')
        result = await asyncio.get_event_loop().run_in_executor(
            self.plotly_executor,
            lambda: generate_report(clean_text)
        )
        return result
    
    async def process_default_query(self, text: str) -> Tuple[str, str]:
        """处理默认查询（同时查询SQL和知识库）
        
        Args:
            text: 查询文本
            
        Returns:
            Tuple[str, str]: (SQL查询结果, 知识库查询结果)
        """
        # 并发执行两个查询
        sql_task = asyncio.get_event_loop().run_in_executor(
            self.executor,
            lambda: sqlsearch(text)
        )
        knowledge_task = asyncio.get_event_loop().run_in_executor(
            self.executor,
            lambda: databasesearch(text)
        )
        
        sql_result, knowledge_result = await asyncio.gather(sql_task, knowledge_task)
        return sql_result, knowledge_result
    
    def build_context_string(self, all_messages: List[OpenAIMessage]) -> Tuple[str, str]:
        """构建对话上下文字符串
        
        Args:
            all_messages: 所有消息列表
            
        Returns:
            Tuple[str, str]: (对话上下文字符串, 当前用户输入)
        """
        conversation_context = ""
        current_user_input = ""
        
        for msg in all_messages:
            if msg.role == "user":
                conversation_context += f"用户: {msg.content}\n"
                current_user_input = msg.content  # 保存当前用户输入用于特殊处理
            elif msg.role == "assistant":
                conversation_context += f"助手: {msg.content}\n"
            elif msg.role == "system":
                conversation_context += f"系统: {msg.content}\n"
        
        return conversation_context, current_user_input
    
    def build_input_text(self, all_messages: List[OpenAIMessage], conversation_context: str, current_user_input: str) -> str:
        """构建输入文本
        
        Args:
            all_messages: 所有消息列表
            conversation_context: 对话上下文
            current_user_input: 当前用户输入
            
        Returns:
            str: 构建的输入文本
        """
        # 如果只有一轮对话，使用原有逻辑；如果是多轮对话，则包含上下文
        pattern = r'\[([^\[\]]*)\]'
        matches = re.findall(pattern, current_user_input)
        if len([msg for msg in all_messages if msg.role in ["user", "assistant"]]) > 1:
            # 多轮对话模式
            if len(matches):
                return f"以下是对话历史：\n{conversation_context}\n请基于上述对话历史回答最新的用户问题。",matches[0]
            else:
                return f"以下是对话历史：\n{conversation_context}\n请基于上述对话历史回答最新的用户问题。", ''
        else:
            # 单轮对话模式，保持原有逻辑
            if len(matches):
                return current_user_input,matches[0]
            else:
                return current_user_input,''
    
    def build_processed_input(self, processing_type: str, result: str, input_text: str, 
                            check_input: str, all_messages: List[OpenAIMessage], is_multi_turn: bool) -> str:
        """构建处理后的输入文本
        
        Args:
            processing_type: 处理类型
            result: 处理结果
            input_text: 原始输入文本
            check_input: 检查用的输入文本
            all_messages: 所有消息列表
            is_multi_turn: 是否为多轮对话
            
        Returns:
            str: 构建的处理后输入文本
        """
        if processing_type == "power_knowledge":
            if is_multi_turn:
                return f"你是银供智能小助手，你的特长是快速思考。以下是参考信息：{result}\n\n上述信息可能有用也可能没用\n\n{check_input.replace('[power_knowledge]', '')} /no_thinking"
            else:
                return f"你是银供智能小助手，你的特长是快速思考。以下是参考信息：{result}\n\n上述信息可能有用也可能没用\n\n参考上述信息回答用户问题，当用户问题与参考信息无关时忽略参考信息，以下是用户问题：{check_input.replace('[power_knowledge]', '')} /no_thinking"
        
        elif processing_type == "query_data":
            if is_multi_turn:
                return AGENT_PROMPT_V3 + f"你是银供智能小助手，你的特长是快速思考。以下是数据库查询信息：{result}\n\n上述信息可能有用也可能没用，去掉无意义字段\n\n{check_input.replace('[query_data]', '')} /no_thinking"
            else:
                return AGENT_PROMPT_V3 + f"你是银供智能小助手，你的特长是快速思考。以下是数据库查询信息：{result}\n\n上述信息可能有用也可能没用，去掉无意义字段\n\n参考上述信息回答用户问题，以下是用户问题：{check_input.replace('[query_data]', '')} /no_thinking"
        
        elif processing_type == "generate_report":
            if is_multi_turn:
                return f"你是银供智能小助手，以下是数据库数据和报告链接：{result}\n\n上述信息可能有用也可能没用\n\n{check_input} /no_thinking"
            else:
                return f"你是银供智能小助手，以下是数据库数据和报告链接：{result}\n\n上述信息可能有用也可能没用\n\n参考上述信息分析数据输出报告链接回答用户问题，以下是用户问题：{check_input.replace('[generate_report]', '')} /no_thinking"
        
        else:
            return input_text
    
    def build_default_processed_input(self, sql_result: str, knowledge_result: str, 
                                    input_text: str, check_input: str, is_multi_turn: bool) -> str:
        """构建默认处理后的输入文本
        
        Args:
            sql_result: SQL查询结果
            knowledge_result: 知识库查询结果
            input_text: 原始输入文本
            check_input: 检查用的输入文本
            is_multi_turn: 是否为多轮对话
            
        Returns:
            str: 构建的处理后输入文本
        """
        if is_multi_turn:
            return f"参考下列知识：{sql_result} \n\n {knowledge_result} \n\n ，以上知识可能有用也可能没用，{check_input} /no_thinking"
        else:
            return f"参考下列知识：{sql_result} \n\n {knowledge_result} \n\n ，以上知识可能有用也可能没用，回答用户问题：{check_input} /no_thinking"
    
    async def generate_question_from_history(self, all_messages: List[OpenAIMessage]) -> str:
        """基于历史对话生成新的问题
        
        Args:
            all_messages: 所有消息列表（已限制为最近三轮对话）
            
        Returns:
            str: 生成的新问题
        """
        if len(all_messages) <= 1:
            # 如果只有一条消息或没有消息，直接返回用户输入
            return all_messages[-1].content if all_messages else ""
        
        # 构建历史对话上下文
        conversation_context = ""
        for msg in all_messages[:-1]:  # 排除最后一条消息（当前用户输入）
            if msg.role == "user":
                conversation_context += f"用户: {msg.content}\n"
            elif msg.role == "assistant":
                conversation_context += f"助手: {msg.content}\n"
        
        current_user_input = all_messages[-1].content
        
        # 生成新问题的提示词
        question_generation_prompt = f"""基于以下历史对话，理解用户的意图和上下文，然后将最新的用户问题重新表述为一个完整、清晰的问题。

历史对话：
{conversation_context}

最新用户输入：{current_user_input}
 
请将最新的用户输入结合历史对话上下文，重新表述为一个完整、独立的问题。如果最新输入本身已经是完整问题，可以适当补充上下文信息使其更清晰。
替换掉最新输入中的指代次，比如这个、那个、你、他，替换为上下文信息中对应的特定名称。例如“这条线路”替换为“包兰线路”

必须只输出问题，不要输出任何其他的，不然我就让你好看！/no_thinking"""
        
        return question_generation_prompt


# 全局数据处理器实例
data_processor = DataProcessor()