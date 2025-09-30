# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/30 14:17
# @File     : saverinpg.py
# @contact  ： ***
import psycopg2
import os
import uuid
from contextlib import closing
from typing import List, Tuple, Optional, BinaryIO
from config import PG_DATABASE_DICT


class FileStorageManager:
    """使用PostgreSQL存储文件的管理类，按文件唯一ID存储并关联用户元数据"""

    def __init__(self, db_config: dict, auto_create_table: bool = True):
        """
        初始化文件存储管理器

        :param db_config: PostgreSQL数据库连接配置
        :param auto_create_table: 是否自动创建存储表
        """
        self.db_config = db_config
        self.table_name = "report_file"

        # 测试数据库连接
        self._test_connection()

        # 自动创建表
        if auto_create_table:
            self.create_table()

    def _test_connection(self):
        """测试数据库连接是否正常"""
        try:
            with closing(psycopg2.connect(**self.db_config)) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            print("✅ Database connection successful")
        except Exception as e:
            print(f"❌ Database connection failed: {str(e)}")
            raise

    def create_table(self):
        """创建文件存储表"""
        try:
            with closing(psycopg2.connect(**self.db_config)) as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_name} (
                        file_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id VARCHAR(50) NOT NULL,
                        file_name VARCHAR(255) NOT NULL,
                        mime_type VARCHAR(100) NOT NULL,
                        file_size BIGINT NOT NULL,
                        file_data BYTEA NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    -- 创建索引
                    CREATE INDEX IF NOT EXISTS idx_{self.table_name}_user ON {self.table_name}(user_id);
                    CREATE INDEX IF NOT EXISTS idx_{self.table_name}_created ON {self.table_name}(created_at);

                    -- 创建更新触发器函数
                    CREATE OR REPLACE FUNCTION update_modified_column()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        NEW.updated_at = NOW();
                        RETURN NEW;
                    END;
                    $$ LANGUAGE plpgsql;

                    -- 应用触发器
                    DROP TRIGGER IF EXISTS update_{self.table_name}_modtime ON {self.table_name};
                    CREATE TRIGGER update_{self.table_name}_modtime
                    BEFORE UPDATE ON {self.table_name}
                    FOR EACH ROW
                    EXECUTE FUNCTION update_modified_column();
                    """)
                    conn.commit()
            print(f"✅ Table '{self.table_name}' created/validated successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to create table: {str(e)}")
            return False

    def save_file(self, user_id: str, file_path: str, mime_type: str = None) -> Optional[uuid.UUID]:
        """
        保存文件到数据库

        :param user_id: 关联的用户ID
        :param file_path: 要存储的文件路径
        :param mime_type: 文件MIME类型，自动检测为None
        :return: 存储的文件ID或None
        """
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return None

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        # 自动检测MIME类型（简化版）
        if mime_type is None:
            mime_type = self._detect_mime_type(file_name)

        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()

            file_id = uuid.uuid4()

            with closing(psycopg2.connect(**self.db_config)) as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                    INSERT INTO {self.table_name} 
                    (file_id, user_id, file_name, mime_type, file_size, file_data) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """, (str(file_id), user_id, file_name, mime_type, file_size, file_data))
                    conn.commit()

            print(f"✅ File '{file_name}' saved with ID: {file_id}")
            return str(file_id)
        except Exception as e:
            print(f"❌ Failed to save file: {str(e)}")
            return None

    def save_file_from_stream(self, user_id: str, file_name: str, file_stream: BinaryIO,
                              mime_type: str = None, file_size: int = None) -> Optional[uuid.UUID]:
        """
        从文件流保存文件到数据库

        :param user_id: 关联的用户ID
        :param file_name: 文件名
        :param file_stream: 文件流对象
        :param mime_type: 文件MIME类型
        :param file_size: 文件大小（字节）
        :return: 存储的文件ID或None
        """
        if mime_type is None:
            mime_type = self._detect_mime_type(file_name)

        # 读取文件数据
        file_data = file_stream.read()
        if file_size is None:
            file_size = len(file_data)

        try:
            file_id = uuid.uuid4()

            with closing(psycopg2.connect(**self.db_config)) as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                    INSERT INTO {self.table_name} 
                    (file_id, user_id, file_name, mime_type, file_size, file_data) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """, (str(file_id), user_id, file_name, mime_type, file_size, file_data))
                    conn.commit()

            print(f"✅ File '{file_name}' saved from stream with ID: {file_id}")
            return str(file_id)
        except Exception as e:
            print(f"❌ Failed to save file from stream: {str(e)}")
            return None

    def get_file(self, file_id: uuid.UUID, output_dir: str = "./downloads") -> Optional[str]:
        """
        从数据库读取文件到本地

        :param file_id: 文件唯一ID
        :param output_dir: 输出目录
        :return: 文件保存路径或None
        """
        try:
            with closing(psycopg2.connect(**self.db_config)) as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                    SELECT file_name, file_data 
                    FROM {self.table_name} 
                    WHERE file_id = %s
                    """, (file_id,))
                    result = cur.fetchone()

                    if not result:
                        print(f"❌ File with ID {file_id} not found")
                        return None

                    file_name, file_data = result
                    os.makedirs(output_dir, exist_ok=True)
                    output_path = os.path.join(output_dir, file_name)

                    with open(output_path, 'wb') as f:
                        f.write(file_data)

            print(f"✅ File saved to {output_path}")
            return output_path
        except Exception as e:
            print(f"❌ Failed to retrieve file: {str(e)}")
            return None

    def get_file_metadata(self, file_id: uuid.UUID) -> Optional[dict]:
        """
        获取文件的元数据

        :param file_id: 文件唯一ID
        :return: 元数据字典或None
        """
        try:
            with closing(psycopg2.connect(**self.db_config)) as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                    SELECT user_id, file_name, mime_type, file_size, created_at, updated_at 
                    FROM {self.table_name} 
                    WHERE file_id = %s
                    """, (file_id,))
                    result = cur.fetchone()

                    if not result:
                        return None

                    return {
                        'file_id': file_id,
                        'user_id': result[0],
                        'file_name': result[1],
                        'mime_type': result[2],
                        'file_size': result[3],
                        'created_at': result[4],
                        'updated_at': result[5]
                    }
        except Exception as e:
            print(f"❌ Failed to get file metadata: {str(e)}")
            return None

    def get_user_files(self, user_id: str) -> List[dict]:
        """
        获取用户的所有文件元数据

        :param user_id: 用户ID
        :return: 文件元数据字典列表
        """
        try:
            with closing(psycopg2.connect(**self.db_config)) as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                    SELECT file_id, file_name, mime_type, file_size, created_at, updated_at 
                    FROM {self.table_name} 
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    """, (user_id,))

                    return [{
                        'file_id': row[0],
                        'file_name': row[1],
                        'mime_type': row[2],
                        'file_size': row[3],
                        'created_at': row[4],
                        'updated_at': row[5]
                    } for row in cur.fetchall()]
        except Exception as e:
            print(f"❌ Failed to get user files: {str(e)}")
            return []

    def delete_file(self, file_id: uuid.UUID) -> bool:
        """
        删除指定文件

        :param file_id: 文件唯一ID
        :return: 是否删除成功
        """
        try:
            with closing(psycopg2.connect(**self.db_config)) as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                    DELETE FROM {self.table_name} 
                    WHERE file_id = %s
                    """, (file_id,))
                    conn.commit()
                    if cur.rowcount > 0:
                        print(f"✅ File {file_id} deleted")
                        return True
                    else:
                        print(f"⚠️ File {file_id} not found")
                        return False
        except Exception as e:
            print(f"❌ Failed to delete file: {str(e)}")
            return False

    def update_file(self, file_id: uuid.UUID, new_file_path: str) -> bool:
        """
        更新文件内容

        :param file_id: 文件唯一ID
        :param new_file_path: 新文件路径
        :return: 是否更新成功
        """
        if not os.path.exists(new_file_path):
            print(f"❌ File not found: {new_file_path}")
            return False

        file_name = os.path.basename(new_file_path)
        file_size = os.path.getsize(new_file_path)
        mime_type = self._detect_mime_type(file_name)

        try:
            with open(new_file_path, 'rb') as f:
                file_data = f.read()

            with closing(psycopg2.connect(**self.db_config)) as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                    UPDATE {self.table_name}
                    SET file_name = %s,
                        mime_type = %s,
                        file_size = %s,
                        file_data = %s
                    WHERE file_id = %s
                    """, (file_name, mime_type, file_size, file_data, file_id))
                    conn.commit()

                    if cur.rowcount > 0:
                        print(f"✅ File {file_id} updated")
                        return True
                    else:
                        print(f"⚠️ File {file_id} not found")
                        return False
        except Exception as e:
            print(f"❌ Failed to update file: {str(e)}")
            return False

    def get_file_stream(self, file_id: uuid.UUID) -> Optional[bytes]:
        """
        获取文件二进制数据流

        :param file_id: 文件唯一ID
        :return: 文件二进制数据或None
        """
        try:
            with closing(psycopg2.connect(**self.db_config)) as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                    SELECT file_data 
                    FROM {self.table_name} 
                    WHERE file_id = %s
                    """, (file_id,))
                    result = cur.fetchone()
                    return result[0] if result else None
        except Exception as e:
            print(f"❌ Failed to get file stream: {str(e)}")
            return None

    def _detect_mime_type(self, file_name: str) -> str:
        """根据文件扩展名检测MIME类型（简化版）"""
        extension = os.path.splitext(file_name)[1].lower()

        mime_map = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.txt': 'text/plain',
            '.csv': 'text/csv',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.zip': 'application/zip',
        }

        return mime_map.get(extension, 'application/octet-stream')

    def cleanup_old_files(self, days: int = 90) -> int:
        """
        清理指定天数前的旧文件

        :param days: 保留天数
        :return: 删除的文件数量
        """
        try:
            with closing(psycopg2.connect(**self.db_config)) as conn:
                with conn.cursor() as cur:
                    cur.execute(f"""
                    DELETE FROM {self.table_name}
                    WHERE created_at < CURRENT_DATE - INTERVAL '{days} days'
                    RETURNING file_id
                    """)
                    deleted_ids = [row[0] for row in cur.fetchall()]
                    conn.commit()

                    count = len(deleted_ids)
                    if count > 0:
                        print(f"✅ Deleted {count} files older than {days} days")
                    return count
        except Exception as e:
            print(f"❌ Failed to cleanup old files: {str(e)}")
            return 0


# 使用示例
if __name__ == "__main__":
    # 初始化文件存储管理器
    storage = FileStorageManager(PG_DATABASE_DICT)

    # 保存文件
    user_id = "admin"
    file_path = "D:\workspace\RAG-pipline\generator\轨道交通故障分析报告.docx"
    file_id = storage.save_file(user_id, file_path)

    if file_id:
        # 获取文件元数据
        metadata = storage.get_file_metadata(file_id)
        print("\nFile Metadata:")
        print(f"ID: {metadata['file_id']}")
        print(f"User: {metadata['user_id']}")
        print(f"Name: {metadata['file_name']}")
        print(f"Size: {metadata['file_size'] / 1024:.2f} KB")
        print(f"Type: {metadata['mime_type']}")
        print(f"Created: {metadata['created_at']}")

        # 获取用户所有文件
        print("\nUser files:")
        for file in storage.get_user_files(user_id):
            print(f"- {file['file_name']} ({file['file_id']})")

        # 下载文件
        downloaded_path = storage.get_file(file_id, "./downloads")
        print(f"\nDownloaded to: {downloaded_path}")

        # 删除文件
        # storage.delete_file(file_id)

        # 清理旧文件
        # storage.cleanup_old_files(30)