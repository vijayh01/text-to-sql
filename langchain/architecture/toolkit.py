import getpass
import os
import sqlite3
import requests
from langchain import hub #type: ignore
from langgraph.prebuilt import create_react_agent #type: ignore
from langchain_openai import ChatOpenAI # type: ignore
from langchain_community.utilities.sql_database import SQLDatabase # type: ignore
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit # type: ignore
from sqlalchemy import create_engine # type: ignore
from sqlalchemy.pool import StaticPool # type: ignore

# database connection object first
def get_engine_for_chinook_db():
    """Pull sql file, populate in-memory database, and create engine."""
    url = "https://raw.githubusercontent.com/lerocha/chinook-database/master/ChinookDatabase/DataSources/Chinook_Sqlite.sql"
    response = requests.get(url)
    sql_script = response.text

    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.executescript(sql_script)
    return create_engine(
        "sqlite://",
        creator=lambda: connection,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )


engine = get_engine_for_chinook_db()
db = SQLDatabase(engine)

# now get the language model
if not os.environ.get("OPENAI_API_KEY"):
  os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter API key for OpenAI: ")
model = ChatOpenAI(model="gpt-4o-mini")

# now get toolkit
toolkit = SQLDatabaseToolkit(db=db, llm=model)
tools = toolkit.get_tools()
print(tools)


# use within an agent
prompt_template = hub.pull("langchain-ai/sql-agent-system-prompt")
assert len(prompt_template.messages) == 1
print(prompt_template.input_variables)
system_message = prompt_template.format(dialect="SQLite", top_k=5)


agent_executor = create_react_agent(
    model=model, 
    tools=toolkit.get_tools(), 
    state_modifier=system_message
)

example_query = "Which country's customers spent the most?"
events = agent_executor.stream(
    {"messages": [("user", example_query)]},
    stream_mode="values",
)
for event in events:
    event["messages"][-1].pretty_print()