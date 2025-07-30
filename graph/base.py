# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/24 15:57
# @File     : base.py
# @contact  ： ***

from typing import Annotated

from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[list, add_messages]


graph_builder = StateGraph(State)


llm = init_chat_model("Qwen3-30B-A3B-FP8",base_url="http://172.26.1.35:8001/v1",model_provider='OpenAI',api_key='empty')


def chatbot(state: State):
    return {"messages": [llm.invoke(state["messages"])]}


# The first argument is the unique node name
# The second argument is the function or object that will be called whenever
# the node is used.
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)
graph = graph_builder.compile()

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from io import BytesIO

try:
    # 获取 Mermaid PNG 数据
    png_data = graph.get_graph().draw_mermaid_png()

    # 转换为图像对象
    img = mpimg.imread(BytesIO(png_data))

    # 使用 Matplotlib 显示
    plt.figure(figsize=(12, 8))
    plt.imshow(img)
    plt.axis('off')  # 不显示坐标轴
    plt.tight_layout()
    plt.show()

except Exception as e:
    print(f"显示图表时出错: {e}")

except Exception as e:
    print(f"Error displaying graph: {e}")

def stream_graph_updates(user_input: str):
    for event in graph.stream({"messages": [{"role": "user", "content": user_input}]}):
        for value in event.values():
            print("Assistant:", value["messages"][-1].content)


while True:
    try:
        user_input = input("User: ")
        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break
        stream_graph_updates(user_input)
    except:
        # fallback if input() is not available
        user_input = "What do you know about LangGraph?"
        print("User: " + user_input)
        stream_graph_updates(user_input)
        break