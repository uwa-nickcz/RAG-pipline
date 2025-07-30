# -*- coding: utf-8 -*-
# @Time    : 2025/4/14 16:39
# @Author  : cz
# @File    : database_operator.py
# @Software: PyCharm
from vector_store.vectorstore import PGVectorStore
from data_loader.data_loader import ContractParser,ContractChunker,get_files
from logger import logger

class DatabaseOperator(PGVectorStore):
    """数据库操作类"""
    def __init__(self,collection_name):
        super(DatabaseOperator, self).__init__(collection_name=collection_name)
        self.parser = ContractParser()
        self.chunker = ContractChunker()

    def create_insert(self,file_path):
        """创建表格并插入数据"""
        all_chunks = []
        documents = get_files(file_path)
        if len(documents) == 0:
            raise Exception("No documents found in the specified directory.")
        for doc_file in documents:
            structured_data = self.parser.parse_document_by_chunk(doc_file)
            all_chunks.extend(self.chunker.generate_chunks(structured_data))

        # 创建向量存储
        self.create_store(all_chunks)
        logger.info(f"创建集合{self.collection_name}")

    def insert(self,file_path):
        """插入数据"""
        all_chunks = []
        documents = get_files(file_path)
        if len(documents) == 0:
            raise Exception("No documents found in the specified directory.")
        for doc_file in documents:
            structured_data = self.parser.parse_document_by_chunk(doc_file)
            all_chunks.extend(self.chunker.generate_chunks(structured_data))
        self.vector_store.add_documents(file_path)


    def delete_documents(self, document_ids):
        self.vector_store.delete(document_ids,collection_only=True)

    def del_collection(self):
        logger.warning(f"删除集合{self.collection_name}")
        self.vector_store.delete_collection()

    def get_collection(self):
        return self.vector_store.get_collection(self.vector_store._make_sync_session())


