# -*- coding: utf-8 -*-
"""
合同解析模块，用于处理和格式化检索到的合同数据
"""
# @Time    : 2025/4/14 15:15
# @Author  : cz
# @File    : contract_parse.py
# @Software: PyCharm

import sys
import os
from typing import Dict, Set, List, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger import logger


class ContractParse:
    """
    合同解析类，用于处理和格式化检索到的合同数据
    
    Attributes:
        structure_data: 从检索器获取的结构化合同数据
        contract_count: 与指定公司相关的合同数量
        contract_info: 格式化后的合同信息文本
    """
    
    def __init__(self, structure_data: List[Any], company: str):
        """
        初始化合同解析器
        
        Args:
            structure_data: 从检索器获取的结构化合同数据
            company: 公司名称，用于过滤相关合同
        """
        self.structure_data = structure_data
        self.contract_count = self.get_count(company)
        self.contract_info = self.get_contract_info(company)
        logger.info(f"**{company}所有合同解析成功**")

    def get_count(self, company: str) -> int:
        """
        获取与指定公司相关的合同数量
        
        Args:
            company: 公司名称
            
        Returns:
            与公司相关的合同数量
        """
        # 使用集合去重获取所有文档标题
        doc_titles: Set[str] = {doc.metadata['doc_title'] for doc in self.structure_data}
        
        # 计算包含公司名称的合同数量
        count = sum(1 for title in doc_titles if company in title)
        
        return count

    def get_contract_info(self, company: str) -> str:
        """
        获取格式化的合同信息文本
        
        Args:
            company: 公司名称，用于过滤相关合同
            
        Returns:
            格式化后的合同信息文本
        """
        # 合并相同标题的文档内容
        doc_contents: Dict[str, str] = {}
        
        # 收集与公司相关的所有文档内容
        for doc in self.structure_data:
            doc_title = doc.metadata['doc_title']
            
            if company in doc_title:
                if doc_title not in doc_contents:
                    doc_contents[doc_title] = doc.page_content
                else:
                    doc_contents[doc_title] += doc.page_content
        
        # 格式化合同信息
        content_prompt = ""
        for doc_title, doc_content in doc_contents.items():
            content_prompt += f"**合同名称**：{doc_title}\n合同内容：{doc_content}\n\n"
        
        return content_prompt