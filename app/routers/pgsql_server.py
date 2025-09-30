# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/8/12 15:43
# @File     : pgsql_server.py
# @contact  ： ***
# vector_routes.py
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from sqlmodel import SQLModel
from uuid import UUID
from pydantic import BaseModel
from database.engins.pgsql import (
    VectorDoc,
    init_db,
    get_all_vectors,
    get_vector_by_id,
    delete_vector as db_delete_vector,
    batch_delete_vectors as db_batch_delete_vectors,
    search_by_metadata as db_search_by_metadata
)

router = APIRouter(tags=["数据库服务"])

# 响应模型（排除大字段）
class VectorDocResponse(BaseModel):
    id: str
    collection_id: Optional[UUID] = None
    document: str
    cmetadata: dict

class PaginatedResponse(BaseModel):
    data: List[VectorDocResponse]
    total: int
    offset: int
    limit: int
    has_more: bool

@router.on_event("startup")
def startup_event():
    """应用启动时初始化数据库"""
    init_db()

@router.get("/pgsql/file", response_model=dict)
def get_all_vectors_api(
        page_num: int = Query(0, description="起始位置", ge=0),
        page_size: int = Query(100, description="每页数量", gt=0, le=1000),
        collection_id: Optional[str] = Query(None, description="集合ID过滤")
):
    """分页查询所有向量文档"""
    offset = page_num
    limit = page_size
    try:
        # 调用数据库操作
        results, total = get_all_vectors(
            offset=offset,
            limit=limit,
            collection_id=collection_id
        )

        # 转换为响应模型
        response_data = [
            VectorDocResponse(
                id=doc.id,
                collection_id=str(doc.collection_id) if doc.collection_id else None,
                cmetadata=doc.cmetadata,
                document=doc.document
            )
            for doc in results
        ]

        # 计算是否有更多数据
        has_more = (offset + limit) < total

        # return PaginatedResponse(
        #     data=response_data,
        #     total=total,
        #     offset=offset,
        #     limit=limit,
        #     has_more=has_more
        # )
        return {
            "data": response_data,
            "total": total,
            "page_num": offset,
            "page_size": limit,
            "has_more": has_more,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vectors/{doc_id}", response_model=VectorDoc)
def get_vector_by_id_api(doc_id: int):
    """根据ID查询单个文档"""
    doc = get_vector_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.delete("/vectors/{doc_id}")
def delete_vector_api(doc_id: int):
    """删除指定ID的向量文档"""
    success = db_delete_vector(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": f"Document {doc_id} deleted successfully"}

@router.post("/pgsql/vectors/batch-delete")
def batch_delete_vectors_api(ids: List[str]):
    """批量删除向量文档"""
    try:
        deleted_count = db_batch_delete_vectors(ids)
        if deleted_count == 0:
            raise HTTPException(status_code=404, detail="No documents found for deletion")
        return {
            "message": f"Deleted {deleted_count} documents",
            "deleted_ids": ids[:deleted_count]  # 实际删除的ID
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))