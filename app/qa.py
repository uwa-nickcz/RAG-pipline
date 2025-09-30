# -*- coding: utf-8 -*-
"""
问答服务模块，提供合同查询和超时检查功能
"""
# @Time    : 2025/4/14 14:58
# @Author  : cz
# @File    : qa.py
# @Software: PyCharm

import sys
import os
import json
import traceback
from typing import Generator, List, Optional, Dict, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from prompt import (
    QUERY_PROMPT,
    QUERY_COMPANY_PROMPT,
    FINAL_QUERY_PROMPT,
    OVERTIME_FINAL_QUERY_PROMPT
)
from config import FRAMEWORK, COLLECTION_NAME
from llm.llm import LLM
from retriever.retriever import PGContractRetriever
from app.contract_parse import ContractParse
from logger import logger, log_exception


# 创建FastAPI应用
app = FastAPI(
    title="合同问答服务",
    description="提供基于RAG的合同查询和超时检查功能",
    version="1.0"
)


class Item(BaseModel):
    """请求数据模型"""
    model: Optional[str] = Field(None, description="使用的模型名称")
    messages: List[Dict[str, Any]] = Field(..., description="消息列表")
    max_tokens: Optional[int] = Field(None, description="最大生成token数")
    temperature: Optional[float] = Field(None, description="温度参数")
    top_p: Optional[float] = Field(None, description="top_p参数")
    stream: Optional[bool] = Field(None, description="是否使用流式响应")


@log_exception(logger)
def process_llm_stream(prompt: str) -> Generator[str, None, None]:
    """
    处理LLM流式响应
    
    Args:
        prompt: 提示词
        
    Yields:
        格式化的流式响应数据
    """
    try:
        for chunk in LLM.steam_call(prompt, engine=FRAMEWORK, show=False):
            chunk_json = chunk.__dict__
            chunk_json['choices'][0] = chunk_json['choices'][0].__dict__
            chunk_json['choices'][0]['delta'] = chunk_json['choices'][0]['delta'].__dict__
            yield f"data: {json.dumps(chunk_json)}\n\n"
    except Exception as e:
        error_message = f"流式响应处理错误: {str(e)}"
        logger.error(error_message)
        logger.debug(f"错误详情: {traceback.format_exc()}")
        # 返回格式化的错误响应
        error_response = {
            "error": {
                "message": str(e),
                "type": "stream_processing_error",
                "code": 500
            }
        }
        yield f"data: {json.dumps(error_response)}\n\n"
        yield "data: [DONE]\n\n"


def get_company_and_query(message: str) -> tuple:
    """
    从用户消息中提取公司名称和查询内容
    
    Args:
        message: 用户消息
        
    Returns:
        (查询内容, 公司名称)的元组
    """
    prompt_query = QUERY_PROMPT.format(usr_question=message)
    company_prompt_query = QUERY_COMPANY_PROMPT.format(usr_question=message)
    
    query = LLM._call(prompt_query).json()['choices'][0]['message']['content']
    company = LLM._call(company_prompt_query).json()['choices'][0]['message']['content']
    
    logger.info(f"【公司】{company}")
    logger.info(f"【查询】{query}")
    
    return query, company


@app.post('/get_is_overtime')
async def get_is_overtime(item: Item):
    """
    检查合同是否超时
    
    Args:
        item: 请求数据
        
    Returns:
        合同超时信息
    """
    message = item.messages[0]['content']
    stream = item.stream
    
    # 获取公司名称和查询内容
    query, company = get_company_and_query(message)
    
    # 创建检索器
    retriever = PGContractRetriever(collection_name=COLLECTION_NAME)
    
    # 获取合同签订时间信息
    time_results = retriever.document_filtered_search(
        '%双方合同签订时间、日期%',
        top_k=8,
        doc_titles=[f'%{company}%']
    )
    
    # 解析合同签订时间
    contract_parse = ContractParse(time_results, company)
    
    # 构建签订时间查询
    time_query = OVERTIME_FINAL_QUERY_PROMPT.format(
        company=company,
        usr_question='所有合同的签订时间分别是多久，简明扼要阐述，json输出',
        count=contract_parse.contract_count,
        contract_info=contract_parse.contract_info
    )
    
    # 获取签订时间
    date_info = LLM._call(time_query).json()['choices'][0]['message']['content']
    
    # 获取交付和违约日期信息
    overtime_info = retriever.document_filtered_search(
        '%产品交付日期、违约日期%',
        top_k=5,
        doc_titles=[f'%{company}%']
    )
    
    # 解析交付和违约信息
    contract_overtime = ContractParse(overtime_info, company)
    
    # 构建最终查询
    final_query = OVERTIME_FINAL_QUERY_PROMPT.format(
        company=company,
        usr_question=f"{message}仅回答结论",
        count=contract_overtime.contract_count,
        contract_info=contract_overtime.contract_info
    )
    
    # 返回结果
    if stream:
        return StreamingResponse(
            process_llm_stream(final_query),
            media_type="text/event-stream"
        )
    else:
        return LLM._call(final_query)


@app.post('/query')
async def query(item: Item):
    """
    查询合同信息
    
    Args:
        item: 请求数据
        
    Returns:
        合同查询结果
    """
    message = item.messages[0]['content']
    stream = item.stream
    
    # 获取公司名称和查询内容
    query, company = get_company_and_query(message)
    
    # 执行查询
    retriever = PGContractRetriever(collection_name=COLLECTION_NAME)
    results = retriever.document_filtered_search(
        f'%{query}%',
        top_k=15,
        doc_titles=[f'%{company}%']
    )
    
    # 解析合同
    contract_parse = ContractParse(results, company)
    
    # 构建最终查询
    if contract_parse.contract_count == 0:
        final_query = FINAL_QUERY_PROMPT.format(
            company=' ',
            usr_question=query,
            count=contract_parse.contract_count,
            contract_info='暂无相关合同信息，请忽略参考，直接回答问题'
        )
    else:
        final_query = FINAL_QUERY_PROMPT.format(
            company=company,
            usr_question=query,
            count=contract_parse.contract_count,
            contract_info=contract_parse.contract_info
        )
    
    # 返回结果
    if stream:
        return StreamingResponse(
            process_llm_stream(final_query),
            media_type="text/event-stream"
        )
    else:
        return LLM._call(final_query)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        "qa:app", 
        host="0.0.0.0", 
        port=9010, 
        reload=True,
        log_level="info"
    )