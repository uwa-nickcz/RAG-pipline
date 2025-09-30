# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/31 16:38
# @File     : langchin_custom.py
# @contact  ： ***
from typing import Any, Dict, Iterator, List, Mapping, Optional
import requests
import json

from langchain_core.callbacks.manager import CallbackManagerForLLMRun
from langchain_core.language_models.llms import LLM
from langchain_core.outputs import GenerationChunk

from config import LLM_API_URL,MODEL

class MyChunk:
    def __init__(self, content):
        self.text = content




class CustomLLM(LLM):
    """A custom chat model that echoes the first `n` characters of the input.

    When contributing an implementation to LangChain, carefully document
    the model including the initialization parameters, include
    an example of how to initialize the model and include any relevant
    links to the underlying models documentation or API.

    Example:

        .. code-block:: python

            model = CustomChatModel(n=2)
            result = model.invoke([HumanMessage(content="hello")])
            result = model.batch([[HumanMessage(content="hello")],
                                 [HumanMessage(content="world")]])
    """

    """The number of characters from the last message of the prompt to be echoed."""

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Run the LLM on the given input.

        Override this method to implement the LLM logic.

        Args:
            prompt: The prompt to generate from.
            stop: Stop words to use when generating. Model output is cut off at the
                first occurrence of any of the stop substrings.
                If stop tokens are not supported consider raising NotImplementedError.
            run_manager: Callback manager for the run.
            **kwargs: Arbitrary additional keyword arguments. These are usually passed
                to the model provider API call.

        Returns:
            The model output as a string. Actual completions SHOULD NOT include the prompt.
        """
        if stop is not None:
            raise ValueError("stop kwargs are not permitted.")

        # 构造请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer empty"
        }

        # 构造请求体（参考 OpenAI Chat Completions API 格式）
        data = {
            "model": MODEL,
            "messages":[
                            {
                                "role": "user",
                                "content":prompt
                            }
                        ],
            "temperature": 0.1,
            "max_tokens": 4096
        }

        # 发送 POST 请求
        response = requests.post(LLM_API_URL, json=data, headers=headers)
        # 正则表达式匹配<think>和</think>之间的内容（包括换行符）
        pattern = r'<think>.*?</think>'
        # 使用re.DOTALL确保.匹配换行符，非贪婪模式.*?避免跨标签匹配

        # 获取响应结果
        if response.status_code == 200:
            result = response.json()
            # return re.sub(pattern, '', result["choices"][0]["message"]["content"], flags=re.DOTALL).strip()
            return result["choices"][0]["message"]["content"]
        else:
            return f"请求失败，状态码：{response.status_code}，{response.text}"


    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        """Stream the LLM on the given prompt.

        This method should be overridden by subclasses that support streaming.

        If not implemented, the default behavior of calls to stream will be to
        fallback to the non-streaming version of the model and return
        the output as a single chunk.

        Args:
            prompt: The prompt to generate from.
            stop: Stop words to use when generating. Model output is cut off at the
                first occurrence of any of these substrings.
            run_manager: Callback manager for the run.
            **kwargs: Arbitrary additional keyword arguments. These are usually passed
                to the model provider API call.

        Returns:
            An iterator of GenerationChunks.
        """

        # 请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer empty"
        }

        # 请求体
        data = {
            "model": MODEL,
            "messages": [
                            {
                                "role": "user",
                                "content":prompt
                            }
                        ],
            "stream": True  # 启用流式响应
        }

        #try:
        # 发起流式请求
        response = requests.post(
            LLM_API_URL,
            headers=headers,
            json=data,
            stream=True  # 重要：保持连接打开
        )

        # 检查响应状态
        if response.status_code != 200:
            raise Exception(f"API 请求失败，状态码: {response.status_code}")

        # 逐块处理流式响应
        for chunk in response.iter_lines():
            if chunk:
                # 解码字节数据
                decoded_chunk = chunk.decode('utf-8')

                # 检查是否为有效数据行（以"data: "开头）
                if decoded_chunk.startswith("data: "):
                    # 提取JSON数据部分
                    json_data = decoded_chunk[6:]

                    # 检查流结束标记
                    if json_data == "[DONE]":
                        break

                    try:
                        # 解析JSON
                        event_data = json.loads(json_data)

                        # 提取内容增量
                        choices = event_data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")

                            # 返回内容增量
                            if content:
                                yield GenerationChunk(text=content)
                    except json.JSONDecodeError:
                        print(f"JSON 解析失败: {json_data}")
                        continue

        # except Exception as e:
        #     yield f"发生错误: {str(e)}"

    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Return a dictionary of identifying parameters."""
        return {
            # The model name allows users to specify custom token counting
            # rules in LLM monitoring applications (e.g., in LangSmith users
            # can provide per token pricing for their model and monitor
            # costs for the given LLM.)
            "model_name": "CustomChatModel",
        }

    @property
    def _llm_type(self) -> str:
        """Get the type of language model used by this chat model. Used for logging purposes only."""
        return "custom"