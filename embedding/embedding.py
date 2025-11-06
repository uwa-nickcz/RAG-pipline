# -*- coding: utf-8 -*-
# @Time    : 2025/4/8 11:02
# @Author  : cz
# @File    : embedding.py
# @Software: PyCharm
import requests
# from sentence_transformers import  util
from config import OLLAMA_API_URL
from requests.exceptions import RequestException, Timeout, ConnectionError

class Embedding:


    def __init__(self, model_name):
        self.model_name = model_name

    @staticmethod
    def get_embedding(input, model="BGE-M3:latest"):
        # 请求数据
        payload = {
            "model": model,  # 指定模型名称
            "input": input,
            "text": input, # 输入文本
        }
        # 发送 POST 请求到 Ollama API
        try:
            response = requests.post(OLLAMA_API_URL, json=payload)

            # 检查响应状态码
            if response.status_code == 200:
                result = response.json()
                embedding = result.get("embeddings", [])
                if len(embedding) == 0:
                    payload['text'] = input[0]
                    response = requests.post(OLLAMA_API_URL, json=payload)
                    if response.status_code == 200:
                        result = response.json()
                        embedding = result.get("embeddings", [])
                        if len(embedding) == 0:
                            embedding = [result.get("data", [])]
                        return embedding
                    elif response.status_code == 500:
                        raise RequestException(f"请求失败，状态码：{response.status_code}")
            else:
                raise RequestException(f"请求失败，状态码：{response.status_code}")

        except Exception as e:
            print("发生错误：", str(e))

#    def evaluate_embedding_model(self,test_case,model="BGE-M3:latest"):
#        results = []
#        self.score = []
#        for case in test_case:
#            embeddings = self.get_embedding([case['anchor'], case['positive'], case['negative']])
#
#            # 计算相似度
#            sim_pos = util.pytorch_cos_sim(embeddings[0], embeddings[1]).item()
#            sim_neg = util.pytorch_cos_sim(embeddings[0], embeddings[2]).item()
#
#            results.append({
#                "case_type": "术语" if "疾病" in case['anchor'] else "同义词" if "模型" in case['anchor'] else "否定",
#                "positive_similarity": sim_pos,
#                "negative_similarity": sim_neg,
#                "passed": sim_pos > sim_neg  # 正例相似度应高于反例
#            })
#        self.score.extend(results)
#        return results

class Embedder(Embedding):
    def __init__(self, model_name):
        super().__init__(model_name)

    def embed_documents(self, texts):
        """
        Call the custom embedding service to get embeddings for a list of documents.
        :param texts: List of text strings to be embedded.
        :return: List of embedding vectors.
        """
        embeddings = self.get_embedding(texts)
        return embeddings

    def embed_query(self, text):
        """
        Call the custom embedding service to get an embedding for a single query.
        :param text: The query text string to be embedded.
        :return: An embedding vector.
        """
        embeddings = self.get_embedding(text)
        return embeddings[0] if embeddings else None
