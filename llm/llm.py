# -*- coding: utf-8 -*-
# @Time    : 2025/4/14 14:06
# @Author  : cz
# @File    : llm.py
# @Software: PyCharm
import requests
from config import LLM_API_URL,OPENAI_API_URL,MODEL
from requests.exceptions import RequestException
from typing import AsyncGenerator, Dict, Any
import aiohttp
from openai import AsyncOpenAI
from typing import AsyncGenerator, Dict, Any
from logger import logger
import re
import json

class LLM:
    def __init__(self, model_name):
        self.model_name = model_name

    @staticmethod
    def _call(input, model=MODEL):
        # 请求数据
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": input
                }
            ],
            "temperature":0,
            "max_tokens":10000,
            "stream":False
        }

        try:
            response = requests.post(LLM_API_URL, json=payload)

            # 检查响应状态码
            if response.status_code == 200:
                result = response.json()
                try:
                    message = result['choices'][0]['message']['content']
                    logger.debug(message)
                    return response
                except:
                    message = re.sub(r'<think>[\s\S]*?<\/think>', '', result['response'], flags=re.DOTALL)
                    logger.debug(message)
                    return message.strip()
            else:
                raise RequestException(f"请求失败，状态码：{response.status_code}")

        except Exception as e:
            print("发生错误：", str(e))



    @staticmethod
    async def steam_call(input_text: str, model: str = MODEL, engine: str = 'vllm', show: bool = True) -> \
    AsyncGenerator[Dict[str, Any], None]:
        """
        异步流式调用大模型

        Args:
            input_text: 输入的文本
            model: 模型名称
            engine: 引擎类型 ('vllm' 或 'ollama')
            show: 是否实时显示输出

        Yields:
            每个生成的文本块
        """
        response_message = ''

        if engine == 'vllm':
            # 配置异步OpenAI客户端
            client = AsyncOpenAI(
                base_url=OPENAI_API_URL,  # vLLM的API地址
                api_key="token-abc123"  # 任意非空字符串
            )

            try:
                # 发起异步流式请求
                stream = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "user", "content": input_text}
                    ],
                    stream=True,
                    temperature=0
                )

                # 异步处理流式输出
                async for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content is not None:
                        response_message += content
                        if show:
                            print(content, end="", flush=True)
                        yield {
                            "content": content,
                            "finished": False,
                            "engine": "vllm"
                        }

                # 返回完整响应
                yield {
                    "content": response_message,
                    "finished": True,
                    "engine": "vllm"
                }

            except Exception as e:
                yield {
                    "error": f"vLLM请求失败: {str(e)}",
                    "finished": True,
                    "engine": "vllm"
                }

        elif engine == 'ollama':
            headers = {"Content-Type": "application/json"}
            data = {
                "model": model,
                "prompt": input_text,
                "max_tokens": 15000,
                "stream": True
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(LLM_API_URL, headers=headers, json=data) as response:
                        async for line in response.content:
                            if line:
                                try:
                                    chunk = json.loads(line.decode("utf-8"))
                                    if not chunk.get("done", False):
                                        content = chunk.get("response", "")
                                        if content:
                                            response_message += content
                                            if show:
                                                print(content, end="", flush=True)
                                            yield {
                                                "content": content,
                                                "finished": False,
                                                "engine": "ollama"
                                            }
                                except json.JSONDecodeError:
                                    continue


            except Exception as e:
                yield {
                    "error": f"Ollama请求失败: {str(e)}",
                    "finished": True,
                    "engine": "ollama"
                }

    # @staticmethod
    # async def stream_generation( model: str = MODEL, api_url=OPENAI_API_URL+'/chat/completions', api_key='empty', messages=None, temperature=0.1, max_tokens=15000):
    #         """流式生成文本的异步生成器函数"""
    #
    #         # 构造请求头
    #         headers = {
    #             "Content-Type": "application/json",
    #             "Authorization": f"Bearer {api_key}"
    #         }
    #
    #         # 构造请求体
    #         data = {
    #             "model": model,
    #             "messages": [msg.dict() for msg in messages],
    #             "temperature": temperature,
    #             "max_tokens": max_tokens,
    #             "stream": True  # 确保API支持流式
    #         }
    #
    #         try:
    #             # 发送POST请求，设置stream=True以获取流式响应
    #             response = requests.post(api_url, json=data, headers=headers, stream=True)
    #             response.raise_for_status()
    #
    #             # 处理流式响应
    #             for line in response.iter_lines():
    #                 if line:
    #                     line = line.decode('utf-8')
    #                     if line.startswith('data: '):
    #                         line = line[6:]  # 移除"data: "前缀
    #
    #                         if line.strip() == '[DONE]':
    #                             break
    #
    #                         try:
    #                             chunk = json.loads(line)
    #                             if 'choices' in chunk and len(chunk['choices']) > 0:
    #                                 delta = chunk['choices'][0].get('delta', {})
    #                                 if 'content' in delta:
    #                                     content = delta['content']
    #                                     # 移除think标签（如果存在）
    #                                     yield content
    #                         except json.JSONDecodeError:
    #                             continue
    #
    #         except requests.exceptions.RequestException as e:
    #             yield f"请求失败: {str(e)}"
    @staticmethod
    async def stream_generation(
            model: str = MODEL,
            api_url=OPENAI_API_URL + '/chat/completions',
            api_key='empty',
            messages=None,
            temperature=0.1,
            max_tokens=15000
    ) -> AsyncGenerator[str, None]:
        """流式生成文本的异步生成器函数"""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        data = {
            "model": model,
            "messages": [msg.dict() for msg in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(api_url, json=data, headers=headers) as response:
                    response.raise_for_status()

                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            line = line[6:]  # 移除"data: "前缀

                            if line.strip() == '[DONE]':
                                break

                            try:
                                chunk = json.loads(line)
                                if 'choices' in chunk and len(chunk['choices']) > 0:
                                    delta = chunk['choices'][0].get('delta', {})
                                    if 'content' in delta:
                                        content = delta['content']
                                        yield content
                            except json.JSONDecodeError:
                                continue

        except aiohttp.ClientError as e:
            yield f"请求失败: {str(e)}"

if __name__ == '__main__':
    input = "你好"
    for chunk in LLM.steam_call(input):
        print(chunk)
    message = LLM.steam_call(input)
