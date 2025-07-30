# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/24 16:20
# @File     : base.py
# @contact  ： ***
import asyncio

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import StructuredMessage
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient

from tools import web_search,weathersearch
from tools.sqlsearch import sqlsearch



# Create an agent that uses the OpenAI GPT-4o model.
model_client = OpenAIChatCompletionClient(
    model="Qwen3-30B-A3B-FP8",
    api_key="YOUR_API_KEY",
    base_url="http://172.26.1.35:8001/v1",
    model_info={
        "vision": 0.1,
        "max_tokens": 8192,
        "function_calling": True,
        "json_output":True,
        "family": "Qwen3",
        "structured_output":False
        }
    )
agent = AssistantAgent(
    name="assistant",
    model_client=model_client,
    tools=[web_search,weathersearch,sqlsearch],
    system_message="Choose tools to solve tasks if its necessary",
)

# Use asyncio.run(agent.run(...)) when running in a script.
# result = asyncio.run(agent.run(task="Find information on AutoGen"))
# print(result.messages)
async def assistant_run_stream() -> None:
    # Option 1: read each message from the stream (as shown in the previous example).
    # async for message in agent.run_stream(task="Find information on AutoGen"):
    #     print(message)

    # Option 2: use Console to print all messages as they appear.
    await Console(
        agent.run_stream(task="查询2025年4月9日当天的缺陷数量"),
        output_stats=True,  # Enable stats printing.
    )


# Use asyncio.run(assistant_run_stream()) when running in a script.
asyncio.run(assistant_run_stream())
