# vector_db.py
from typing import List, Optional
from sqlmodel import SQLModel, Field, create_engine, Session, select, delete
from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, func
import sys
from uuid import UUID
sys.path.append("../../")
from config import PG_DATABASE_URL

# 数据库配置
DATABASE_URL = PG_DATABASE_URL
engine = create_engine(DATABASE_URL, echo=True)

class VectorDoc(SQLModel, table=True):
    __tablename__ = 'langchain_pg_embedding'
    id: Optional[int] = Field(default=None, primary_key=True)
    collection_id: Optional[UUID] = Field(default=None)
    document: str = Field(default=None)
    embedding: List[float] = Field(sa_type=Vector(1536))  # OpenAI向量维度
    cmetadata: dict = Field(default={}, sa_type=JSON)

def init_db():
    """初始化数据库表结构"""
    SQLModel.metadata.create_all(engine)

def get_all_vectors(
        offset: int = 0,
        limit: int = 100,
        collection_id: Optional[str] = None
) :
        """
        分页查询所有向量文档
        返回: (当前页结果列表, 总记录数)
        """
        with Session(engine) as session:
            # 基础查询
            statement = select(VectorDoc)

            # 添加集合ID过滤
            if collection_id:
                statement = statement.where(
                    VectorDoc.collection_id == collection_id
                )

            # 获取总数
            count_statement = select(func.count()).select_from(statement.subquery())
            total = session.exec(count_statement).one()

            # 分页查询
            statement = statement.offset(offset).limit(limit)
            results = session.exec(statement).all()
            return results, total

def get_vector_by_id(doc_id: int) -> Optional[VectorDoc]:
    """根据ID查询单个文档"""
    with Session(engine) as session:
        return session.get(VectorDoc, doc_id)

def delete_vector(doc_id: int) -> bool:
    """删除指定ID的向量文档"""
    with Session(engine) as session:
        doc = session.get(VectorDoc, doc_id)
        if doc:
            session.delete(doc)
            session.commit()
            return True
        return False

def batch_delete_vectors(ids: List[int]) -> int:
    """批量删除向量文档"""
    with Session(engine) as session:
        result = session.exec(
            delete(VectorDoc).where(VectorDoc.id.in_(ids)))
        session.commit()
        return result.rowcount

def search_by_metadata(key: str, value: str) -> List[VectorDoc]:
    """根据元数据键值对查询文档"""
    with Session(engine) as session:
        statement = select(VectorDoc).where(
            VectorDoc.cmetadata[key].astext == value
        )
        return session.exec(statement).all()