from vanna.base import VannaBase
import re


def generation(model,api_url,api_key,prompt,**kwargs):
    import requests

    # 设置 API 地址和密钥（如果有的话）
    API_URL = api_url
    API_KEY = api_key  # 如果不需要认证，可以设为 EMPTY

    # 构造请求头
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    # 构造请求体（参考 OpenAI Chat Completions API 格式）
    data = {
        "model": model,
        "messages":
            prompt
        ,
        "temperature": 0.1,
        "max_tokens": 20000
    }

    # 发送 POST 请求
    response = requests.post(API_URL, json=data, headers=headers)
    # 正则表达式匹配<think>和</think>之间的内容（包括换行符）
    pattern = r'<think>.*?</think>'
    # 使用re.DOTALL确保.匹配换行符，非贪婪模式.*?避免跨标签匹配

    # 获取响应结果
    if response.status_code == 200:
        result = response.json()
        return re.sub(pattern, '', result["choices"][0]["message"]["content"], flags=re.DOTALL).strip()
    else:
        return f"请求失败，状态码：{response.status_code}，{response.text}"


class Vllmqwen(VannaBase):
    def __init__(self, config=None):
        if config is None:
            raise ValueError(
                "For vllm, config must be provided with amodel"
            )

        if "model" not in config:
            raise ValueError("config must contain a Vllm model")

        self.model = config["model"]
        self.api_url = config["api_url"]
        self.api_key = config["api_key"]

    def system_message(self, message: str) -> any:
        return {"role": "system", "content": message}

    def user_message(self, message: str) -> any:
        return {"role": "user", "content": message}

    def assistant_message(self, message: str) -> any:
        return {"role": "assistant", "content": message}

    def generate_sql(self, question: str,allow_llm_to_see_data=True, **kwargs) -> str:
        # Use the super generate_sql
        sql = super().generate_sql(question, **kwargs)

        # Replace "\_" with "_"
        sql = sql.replace("\\_", "_")

        return sql

    def submit_prompt(self, prompt, **kwargs) -> str:
        return generation(model=self.model,prompt=prompt,api_url=self.api_url,api_key=self.api_key)

    def generation(self,model, api_url, api_key, prompt, **kwargs):
        import requests

        # 设置 API 地址和密钥（如果有的话）
        API_URL = api_url
        API_KEY = api_key  # 如果不需要认证，可以设为 EMPTY

        # 构造请求头
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }

        # 构造请求体（参考 OpenAI Chat Completions API 格式）
        data = {
            "model": model,
            "messages":
                prompt
            ,
            "temperature": 0.1,
            "max_tokens": 4096
        }

        # 发送 POST 请求
        response = requests.post(API_URL, json=data, headers=headers)
        # 正则表达式匹配<think>和</think>之间的内容（包括换行符）
        pattern = r'<think>.*?</think>'
        # 使用re.DOTALL确保.匹配换行符，非贪婪模式.*?避免跨标签匹配

        # 获取响应结果
        if response.status_code == 200:
            result = response.json()
            return re.sub(pattern, '', result["choices"][0]["message"]["content"], flags=re.DOTALL).strip()
        else:
            return f"请求失败，状态码：{response.status_code}，{response.text}"


