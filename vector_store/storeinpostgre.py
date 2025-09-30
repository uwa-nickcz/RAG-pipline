# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/25 15:14
# @File     : storeinpostgre.py
# @contact  ： ***
import psycopg2
import pandas as pd
import numpy as np
from embedding.embedding import Embedder
from vanna.base import VannaBase
from vector_store.vectorstore import PGVectorStore
from langchain_postgres.vectorstores import PGVector
from config import PG_DATABASE_URL
import json
import pandas as pd
import uuid

class PostgreSQLVectorDB(VannaBase):
    def __init__(self, config=None,collection_name = 'qingdao'):
        # 默认配置
        VannaBase.__init__(self, config=config)
        self.pgvectorStore = PGVectorStore(collection_name=collection_name,embed_model="bge-m3:latest")
        self.embedder = Embedder("bge-m3:latest")
        self.collection_name = collection_name
        self.ddl_store = PGVector(
            collection_name=collection_name+'-ddl',
            embeddings=self.embedder,
            connection=PG_DATABASE_URL,
            create_extension=False
        )
        self.doc_store = PGVector(
            collection_name=collection_name+'-doc',
            embeddings=self.embedder,
            connection=PG_DATABASE_URL,
            create_extension=False
        )
        self.qa_store = PGVector(
            collection_name=collection_name+'-question&sql',
            embeddings=self.embedder,
            connection=PG_DATABASE_URL,
            create_extension=False
        )


    def add_ddl(self, ddl: str, **kwargs) -> str:
        metadata = [{'id': str(uuid.uuid4()) + "-ddl"}]
        self.pgvectorStore.create_store_form_text([ddl], collection_name=self.collection_name+'-ddl',metadatas=metadata)
        return metadata
    def add_documentation(self, doc: str, **kwargs) -> str:
        metadata = [{'id': str(uuid.uuid4()) + "-doc"}]
        self.pgvectorStore.create_store_form_text([doc], collection_name=self.collection_name+'-doc',metadatas=metadata)
        return metadata

    def add_question_sql(self, question: str, sql: str, **kwargs) -> str:
        question_sql_json = json.dumps(
            {
                "question": question,
                "sql": sql,
            },
            ensure_ascii=False,
        )
        metadata = [{'id':str(uuid.uuid4()) + "-sql"}]
        return  self.pgvectorStore.create_store_form_text([question_sql_json],collection_name=self.collection_name+'-question&sql'
                                                          ,metadatas=metadata)

    def get_related_ddl(self, question: str, **kwargs) -> list:
        results = self.ddl_store.similarity_search(question, k=1,**kwargs)
        answer_list = [result.page_content for result in results]
        return answer_list

    def get_related_documentation(self, question: str, **kwargs) -> list:
        results = self.doc_store.similarity_search(question, **kwargs)
        answer_list = [result.page_content for result in results]
        return answer_list
    def get_similar_question_sql(self, question: str, **kwargs) -> list:
        results = self.qa_store.similarity_search(question, **kwargs)
        answer_list = [result.page_content for result in results]
        return [json.loads(answer) for answer in answer_list]

    def get_training_data(self, **kwargs) -> pd.DataFrame:
        return pd.DataFrame([1,2,3])

    def remove_training_data(self,id: str, **kwargs) -> bool:
        try:
            self.ddl_store.delete([id],collection_only=True)
            self.doc_store.delete([id], collection_only=True)
            self.qa_store.delete([id], collection_only=True)
            return True
        except:
            return False

    def generate_embedding(self, data: str, **kwargs) :
        return self.embedder.embed_query(data)