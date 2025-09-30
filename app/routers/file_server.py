# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/30 16:22
# @File     : file_server.py
# @contact  ： ***
# routers/file_server.py

from fastapi import APIRouter, HTTPException, Response
from generator.saverinpg import FileStorageManager, PG_DATABASE_DICT

router = APIRouter(prefix="/files", tags=["文件服务"])

storage_manager = FileStorageManager(PG_DATABASE_DICT, auto_create_table=False)

@router.get("/download/{file_id}")
async def download_file(file_id: str):
    file_data = storage_manager.get_file_stream(file_id)
    if not file_data:
        raise HTTPException(status_code=404, detail="File not found")

    file_metadata = storage_manager.get_file_metadata(file_id)
    if not file_metadata:
        raise HTTPException(status_code=404, detail="File metadata not found")

    filename = file_metadata.get('file_name', 'download')
    mime_type = file_metadata.get('mime_type', 'application/octet-stream')

    encoded_filename = filename.encode('utf-8').decode('latin-1')
    headers = {
        'Content-Disposition': f'attachment; filename="{encoded_filename}"',
        'Content-Type': mime_type,
    }

    return Response(content=file_data, headers=headers, media_type=mime_type)

@router.get("/{file_id}")
async def get_file_info(file_id: str):
    metadata = storage_manager.get_file_metadata(file_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="File not found")
    return metadata

@router.get("/users/{user_id}/files")
async def list_user_files(user_id: str):
    files = storage_manager.get_user_files(user_id)
    return files