# -*- coding: utf-8 -*-
import os
import requests
import json
from io import BytesIO
from config import DeptNoYinchuan

access_token = ""  # 使用模块级变量替代global


def upload_file_to_ftp(
        file_data,
        ip='172.26.1.89',
        port='9527',
        ext = 'jpg'
):
    """上传文件到FTP服务

    Args:
        file_data: 可以是文件路径(str)或字节数据(bytes)
        ip: 服务器IP
        port: 服务器端口
    """
    global access_token

    # 准备文件数据
    if isinstance(file_data, str) and os.path.isfile(file_data):
        # 处理文件路径
        filename = os.path.basename(file_data)
        ext = os.path.splitext(filename)[1][1:]  # 提取扩展名
        with open(file_data, 'rb') as f:
            file_bytes = f.read()
    elif isinstance(file_data, bytes):
        # 处理字节数据
        file_bytes = file_data
        filename = "upload_file"  # 默认文件名
    else:
        return {"success": False, "error": "Invalid file data type"}

    # 创建内存文件对象
    file_obj = BytesIO(file_bytes)
    files = {'file': (filename, file_obj, f'application/octet-stream')}

    # url = f"http://{ip}:{port}/cms/api/common/uploadFtpFromPy"
    url = f"http://{ip}:{port}/itps/cms/api/common/uploadFtpFromPy"
    headers = {"Authorization": f"bearer {access_token}"}
    data = {"deptNo": DeptNoYinchuan, "extName": ext}

    try:
        # 第一次尝试上传
        response = requests.post(url, files=files, data=data, headers=headers, timeout=30)
        response.raise_for_status()
        result = response.json()

        if result.get('status') == 200:
            return result['data']['fullPathEncode']

        # 处理token过期情况
        if result.get('status') == 401:
            access_token = get_access_token("172.26.1.89", "9527", 'itps-cdtyeai-client', 'Cdtye@2024')
            if not access_token:
                return {"success": False, "error": "Failed to refresh access token"}

            headers["Authorization"] = f"bearer {access_token}"
            file_obj.seek(0)  # 重置文件指针

            # 重新上传
            response = requests.post(url, files=files, data=data, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()

            if result.get('status') == 200:
                return result['data']['fullPathEncode']
            else:
                return {"success": False, "error": f"Upload failed after token refresh: {result}"}

        return {"success": False, "error": f"Upload failed: {result}"}

    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Request failed: {str(e)}"}
    except json.JSONDecodeError:
        return {"success": False, "error": "Response format error", "raw_response": response.text}
    finally:
        file_obj.close()  # 确保关闭文件对象


def get_access_token(
        ip: str,
        port: str,
        client_id: str,
        client_secret: str,
        grant_type: str = "client_credentials"
) -> str:
    """获取访问令牌"""
    url = f"http://{ip}:{port}/itps/auth/oauth/token"
    data = {
        "grant_type": grant_type,
        "client_id": client_id,
        "client_secret": client_secret
    }

    try:
        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        return response.json()['access_token']
    except Exception as e:
        print(f"Token request failed: {str(e)}")
        return ""


if __name__ == "__main__":
    # 使用文件路径上传
    # result = upload_file_to_ftp('test.jpg')
    # print(result)

    # 使用字节数据上传
    with open('test.jpg', 'rb') as f:
        image_bytes = f.read()
    result = upload_file_to_ftp(image_bytes)
    print(result)