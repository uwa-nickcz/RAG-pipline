# -*- coding: utf-8 -*-
# @Time    : 2025/4/11 9:40
# @Author  : cz
# @File    : vectorstore.py
# @Software: PyCharm
# 向量操作类
from typing import List
#from database.model.documentchunk import create_tables, DocumentChunk
# from database.engins import SessionLocal
# from embedding.embedding import Embedding
from langchain_postgres.vectorstores import PGVector
from embedding.embedding import Embedder
from config import PG_DATABASE_URL
import logging


# class VectorStore:
#     def __init__(self):
#         # enable_pgvector()
#         create_tables()
#         self.session = SessionLocal()
#
#     def __enter__(self):
#         return self
#
#     def __exit__(self, exc_type, exc_val, exc_tb):
#         self.session.close()
#
#     def create_embedding(self, text: str) -> List[float]:
#         """使用嵌入模型生成向量"""
#         return Embedding.get_embedding(text)[0]
#
#     def store_chunk(self, document_id: str, chunk_index: int, text: str):
#         """存储文档块及其向量"""
#         embedding = self.create_embedding(text)
#         chunk = DocumentChunk(
#             content=text,
#             embedding=embedding,
#             document_id=document_id,
#             chunk_index=chunk_index
#         )
#         self.session.add(chunk)
#         self.session.commit()
#
#     def similarity_search(self, query: str, k: int = 5) -> List[DocumentChunk]:
#         """相似度搜索"""
#         query_embedding = self.create_embedding(query)
#
#         results = self.session.query(DocumentChunk).order_by(
#             DocumentChunk.embedding.cosine_distance(query_embedding)
#         ).limit(k).all()
#
#         return results



class PGVectorStore():
    """使用pgvector的向量存储类"""
    def __init__(self,collection_name="test",embed_model="bge-m3:latest"):
        super().__init__()
        self.collection_name = collection_name
        self.embedder = Embedder(embed_model)
        self.vector_store = PGVector(
            collection_name=collection_name,
            embeddings=self.embedder,
            connection=PG_DATABASE_URL,
            create_extension=False
        )

    def create_store(self, chunks,collection_name):
        return PGVector.from_documents(
            documents=chunks,
            embedding=self.embedder,
            collection_name=collection_name,
            connection =PG_DATABASE_URL,
            use_jsonb=True,
            pre_delete_collection=False,
            create_extension=False
        )

    def create_store_form_text(self, chunks,collection_name,metadatas):
        return PGVector.from_texts(
            texts=chunks,
            embedding=self.embedder,
            collection_name=collection_name,
            connection =PG_DATABASE_URL,
            use_jsonb=True,
            pre_delete_collection=False,
            create_extension=False,
            metadatas=metadatas
        )

    def get_retriever(self):
        # 使用PGVector来创建retriever
        return self.vector_store.as_retriever(
            search_kwargs={"k": 5, "filter": {}}
        )


    def delete_documents(self, document_ids):
        self.vector_store.delete(document_ids,collection_only=True)

    def del_collection(self):
        logging.warning(f"删除集合{self.collection_name}")
        self.vector_store.delete_collection()



# 使用示例
# if __name__ == "__main__":
#     # 初始化存储
#     with VectorStore() as store:
#         # 存储示例文档
#         store.store_chunk(
#             document_id="doc_001",
#             chunk_index=0,
#             text="pgvector是一个PostgreSQL扩展，支持向量相似度搜索"
#         )
#
#         # 执行搜索
#         results = store.similarity_search("PostgreSQL的向量扩展是什么？")
#
#         print("Top 5相似结果：")
#         for chunk in results:
#             print(f"文档ID: {chunk.document_id}, 内容: {chunk.content[:50]}...")