import urllib.parse
from langchain import hub 
from sqlalchemy import text
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.agents import create_sql_agent
from langchain.agents.agent_types import AgentType
from langchain.memory import ConversationBufferMemory 
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.chat_message_histories import SQLChatMessageHistory 
from langchain_community.utilities import SQLDatabase
from langchain_experimental.tools import PythonREPLTool
from langchain_deepseek import ChatDeepSeek
from constants import LLM_MODEL_NAME
import streamlit as st

CUSTOM_SUFFIX = """Begin!

Relevant pieces of previous conversation:
{chat_history}

Question: {input}

Always follow these rules:
1. If showing counts/numbers, use format: "Result: [NUMBER]"
2. For list results, use: "Result: [ITEM1], [ITEM2], ..."
3. For complex results, create a markdown table
4. If no results found, say "Result: No data found"

Example response for customer count:
Thought: I need to count customers in China
Action: Query database
Observation: 100,939
Final Answer: Result: 100,939

{agent_scratchpad}"""

# CUSTOM_SUFFIX = """Begin!

# Relevant pieces of previous conversation:
# {chat_history}
# (Note: Only reference this information if it is relevant to the current query.)

# Question: {input}
# Thought Process: It is imperative that I do not fabricate information not present in any table or engage in hallucination; maintaining trustworthiness is crucial.
# In SQL queries involving string or TEXT comparisons like first_name, I must use the `LOWER()` function for case-insensitive comparisons and the `LIKE` operator for fuzzy matching. 
# Queries for return percentage is defined as total number of returns divided by total number of orders. You can join orders table with users table to know more about each user.
# Make sure that query is related to the SQL database and tables you are working with.
# If the result is empty, the Answer should be "No results found". DO NOT hallucinate an answer if there is no result.

# My final response should STRICTLY be the output of SQL query.

# {agent_scratchpad}
# """


DEEPSEEK_API_KEY = st.secrets["deepseek"]["DEEPSEEK_API_KEY"]
langchain_chat_kwargs = {
    "temperature": 0,
    "max_tokens": 4000,
    "verbose": True,
}
chat_deepseek_model_kwargs = {
    "top_p": 1.0,
    "frequency_penalty": 0.0,
    "presence_penalty": -1,
}

def get_chat_deepseek(model_name):
    """
    Returns an instance of the ChatDeepSeek class initialized with the specified model name.
    Args:
        model_name (str): The name of the model to use.
    Returns:
        ChatDeepSeek: An instance of the ChatDeepSeek class.
    """
    llm = ChatDeepSeek(
        model=model_name,
        api_key=DEEPSEEK_API_KEY,
        model_kwargs=chat_deepseek_model_kwargs, 
        **langchain_chat_kwargs
    )
    return llm


def get_sql_toolkit(tool_llm_name: str):
    """
    Instantiates a SQLDatabaseToolkit object with the specified language model.
    This function creates a SQLDatabaseToolkit object configured with a language model
    obtained by the provided model name. The SQLDatabaseToolkit facilitates SQL query
    generation and interaction with a database.

    Args:
        tool_llm_name (str): The name or identifier of the language model to be used.
    Returns:
        SQLDatabaseToolkit: An instance of SQLDatabaseToolkit initialized with the provided language model.
    """
    llm_tool = get_chat_deepseek(model_name=tool_llm_name)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm_tool)
    return toolkit


def get_agent_llm(agent_llm_name: str):
    """
    Retrieve a language model agent for conversational tasks.

    Args:
        agent_llm_name (str): The name or identifier of the language model for the agent.
    Returns:
        ChatDeepSeek: A language model agent configured for conversational tasks.
    """
    llm_agent = get_chat_deepseek(model_name=agent_llm_name)
    return llm_agent


def initialize_python_agent(agent_llm_name: str = LLM_MODEL_NAME):
    """
    Create an agent for Python-related tasks.

    Args:
        agent_llm_name (str): The name or identifier of the language model for the agent.
    Returns:
        AgentExecutor: An agent executor configured for Python-related tasks.
    """
    instructions = """You are an agent designed to write Plotly visualization code. Follow these rules STRICTLY:
    1. ALWAYS return code wrapped in EXACTLY ONE ```python block
    2. Use THIS EXACT structure:
    ```python
    import pandas as pd
    import plotly.express as px
    
    # Create sample data (REPLACE WITH ACTUAL DATA FROM QUERY)
    df = pd.DataFrame({
        'gender': ['Male', 'Female', 'Other'],
        'count': [1200, 1500, 300]
    })
    
    # Create plot
    fig = px.bar(df, x='gender', y='count', title='User Distribution by Gender')
    fig.update_layout(
        xaxis_title='Gender',
        yaxis_title='Number of Users',
        template='plotly_white'
    )
    ```
    3. NEVER include anything outside the code block
    4. ALWAYS include actual data from the query
    5. ALWAYS include proper labels and titles
    6. NEVER use fig.show()"""

    base_prompt = hub.pull("langchain-ai/openai-functions-template")
    prompt = base_prompt.partial(instructions=instructions)
    tools = [PythonREPLTool()]
    agent = create_openai_functions_agent(
        llm=get_chat_deepseek(LLM_MODEL_NAME),
        tools=tools,
        prompt=prompt
    )    
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    return agent_executor


def initialize_sql_agent(db_config):
    """Initialize SQL agent with proper validation"""
    required_fields = ['USER', 'PASSWORD', 'HOST', 'DATABASE', 'PORT']
    
    # Validate config
    if not db_config or not isinstance(db_config, dict):
        raise ValueError("Invalid database configuration")
        
    # Check required fields
    for field in required_fields:
        if field not in db_config or not db_config[field]:
            raise ValueError(f"Missing required field: {field}")
    
    try:
        llm = get_chat_deepseek(LLM_MODEL_NAME)
        
        # Create database connection
        password = urllib.parse.quote_plus(db_config['PASSWORD'])
        connection_string = (
            f"mysql+pymysql://{db_config['USER']}:{password}@"
            f"{db_config['HOST']}:{db_config['PORT']}/{db_config['DATABASE']}"
        )
        # Connection validation
        db = SQLDatabase.from_uri(connection_string)
        with db._engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # Create toolkit with LLM
        toolkit = SQLDatabaseToolkit(
            db=db,
            llm=llm
        )
        
        message_history = SQLChatMessageHistory(
            session_id="my-session",
            connection_string = (
            f"mysql+pymysql://{db_config['USER']}:{password}@"
            f"{db_config['HOST']}:{db_config['PORT']}/{db_config['DATABASE']}"), 
            table_name="message_store",
            session_id_field_name="session_id"
        )
        memory = ConversationBufferMemory(memory_key="chat_history", input_key='input', chat_memory=message_history, return_messages=False) #added recently

        # Create and return agent
        return create_sql_agent(
        llm=llm,
        toolkit=toolkit,
        agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        suffix=CUSTOM_SUFFIX,
        verbose=True,
        max_iterations=5,
        handle_parsing_errors=True,
        agent_executor_kwargs={
            "memory": memory,
            "max_execution_time": 30,
            "handle_parsing_errors": True
        }
    )
    except Exception as e:
        raise ValueError(f"Failed to initialize SQL agent: {str(e)}")
