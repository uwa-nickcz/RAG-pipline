from langchain.agents import AgentExecutor, create_tool_calling_agent,initialize_agent,AgentType
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate


from tools import databasesearch,sqlsearch,generate_report
from prompt import AGENT_PROMPT_Mermaid,AGENT_PROMPT_WEB
from config import OPENAI_API_URL,MODEL

llm = ChatOpenAI(
    openai_api_base=OPENAI_API_URL,
    openai_api_key="your-api-key",
    model_name=MODEL,
    streaming=True,
    temperature=0.1
)

# 创建智能体
prompt_for_metahuman = ChatPromptTemplate.from_messages([
    ("system", AGENT_PROMPT_Mermaid),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}")
])
agent_for_metahuman = create_tool_calling_agent(llm, [databasesearch, sqlsearch], prompt_for_metahuman)
agent_executor_for_metahuman = AgentExecutor(
    agent=agent_for_metahuman,
    tools=[databasesearch, sqlsearch],
    verbose=True,
    max_iterations=5,
    handle_parsing_errors=True
)

prompt_for_web = ChatPromptTemplate.from_messages([
    ("system", AGENT_PROMPT_WEB),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}")
])
agent_for_web = create_tool_calling_agent(llm, [databasesearch, sqlsearch,generate_report], prompt_for_web)
agent_executor_web = AgentExecutor(
    agent=agent_for_web,
    tools=[databasesearch, sqlsearch,generate_report],
    verbose=True,
    max_iterations=5,
    handle_parsing_errors=True
)


prompt_for_v3 = ChatPromptTemplate.from_messages([
    ("system", '你是银供电智能小助手'),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}")
])
agent_for_v3  = create_tool_calling_agent(llm, [], prompt_for_v3)
agent_executor_for_v3 = AgentExecutor(
    agent=agent_for_v3,
    verbose=True,
    tools=[],
    max_iterations=5,
    handle_parsing_errors=True
)


# 创建适合链的提示模板（移除了agent_scratchpad）
prompt_for_chain = ChatPromptTemplate.from_messages([
    ("system", '你是银供电智能小助手'),
    ("placeholder", "{chat_history}"),
    ("human", "{input}"),
])

# 创建简单的LLMChain
chain = prompt_for_chain | llm