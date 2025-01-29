import os
import sys
import time
import warnings
import streamlit as st
import unidecode
import pymysql
from pymysql import Error
from sqlalchemy.sql import text
from langchain_community.utilities import SQLDatabase
import urllib.parse
from helper import display_code_plots, display_text_with_images
from llm_agent import initialize_python_agent, initialize_sql_agent
from constants import LLM_MODEL_NAME
from sqlalchemy import create_engine, exc, text


DEEPSEEK_API_KEY = st.secrets["deepseek"]["DEEPSEEK_API_KEY"]
st.set_page_config(page_title="SQL and Python Agent")

### TEST DEEPSEEK API CONNECTION ###
import os
from langchain_deepseek import ChatDeepSeek
def test_deepseek():
    client = ChatDeepSeek(
        api_key=DEEPSEEK_API_KEY,
        model=LLM_MODEL_NAME,
        max_tokens=50
    )
    try:
        messages = [
                ("system","You are a helpful assistant that translates English to French. Translate the user sentence.",),
                ("human", "I love programming."),]
        response = client.invoke(messages)
        print("API Response:", response)
        return True
    except Exception as e:
        print("API Error:", str(e))
        return False
if test_deepseek():
    st.success("DeepSeek API connection successful!")
else:
    st.error("DeepSeek API connection failed. Check your key and credits.")
### TEST DEEPSEEK API CONNECTION ###



if "db_config" not in st.session_state:
    st.session_state.db_config = {
        'USER': '',
        'PASSWORD': '',
        'HOST': 'localhost',
        'DATABASE': '',
        'PORT': '3306'
    }

if "db_connected" not in st.session_state:
    st.session_state.db_connected = False

if 'databases' not in st.session_state:
    st.session_state.databases = []

# 2. Sidebar user inputs.
st.sidebar.title("DATABASE CONFIGURATION")
st.sidebar.subheader("Enter MySQL connection details:", divider=True)

user = st.sidebar.text_input("User", value=st.session_state.db_config['USER'])
password = st.sidebar.text_input("Password", type="password", value=st.session_state.db_config['PASSWORD'])
host = st.sidebar.text_input("Host", value=st.session_state.db_config['HOST'])
port = st.sidebar.text_input("Port", value=st.session_state.db_config['PORT'])

# 3. Single dynamic button label.
button_label = "Save and Connect" if not st.session_state.db_connected else "Update Connection"

def test_connection(config):
    """Check DB connectivity and, if successful, fetch all databases."""
    try:
        connection_string = (
            f"mysql+pymysql://{config['USER']}:{urllib.parse.quote_plus(config['PASSWORD'])}"
            f"@{config['HOST']}:{config['PORT']}/"
        )
        engine = create_engine(connection_string)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # If we succeed, fetch list of databases for the dropdown
        try:
            with pymysql.connect(
                host=config['HOST'],
                user=config['USER'],
                password=config['PASSWORD'],
                port=int(config['PORT']),  # Convert port to integer
                cursorclass=pymysql.cursors.DictCursor
            ) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SHOW DATABASES")
                    dbs = [db['Database'] for db in cursor.fetchall() 
                        if db['Database'] not in ('sys', 'mysql','performance_schema','information_schema')]
                return True, dbs
        except Error as e:
            st.sidebar.error(f"Error fetching databases: {e}")
            return False, []
    except Exception as e:
        st.sidebar.error(f"Connection test failed: {str(e)}")
        return False, []
    return False, []

if st.sidebar.button(button_label):
    if all([user, password, host, port]):
        new_config = {
            'USER': user,
            'PASSWORD': password,
            'HOST': host,
            'PORT': port,
            'DATABASE': ''
        }
        ok, db_list = test_connection(new_config)
        if ok:
            st.session_state.db_config = new_config
            st.session_state.db_connected = True
            st.session_state.databases = db_list
            st.sidebar.success("Connection test successful! Please select a database.")
        else:
            st.session_state.db_connected = False
            st.session_state.databases = []
    else:
        st.sidebar.error("All fields are required")

if st.session_state.db_connected and st.session_state.databases:
    db_choice = st.sidebar.selectbox(
        "Select Database",
        options=st.session_state.databases,
        index=st.session_state.databases.index(st.session_state.db_config['DATABASE'])
        if st.session_state.db_config['DATABASE'] in st.session_state.databases else 0
    )
    
    if db_choice and db_choice != st.session_state.db_config['DATABASE']:
        st.session_state.db_config['DATABASE'] = db_choice
        try:
            st.session_state.sql_agent = initialize_sql_agent(st.session_state.db_config)
            st.session_state.python_agent = initialize_python_agent()
            st.sidebar.success(f"Connected to {db_choice}!")
        except Exception as e:
            st.session_state.db_config['DATABASE'] = ''
            st.sidebar.error(f"Connection to {db_choice} failed: {str(e)}")

st.title("DEEPSEEK SQL DASHBOARD AGENT")
st.write("This agent can help you with SQL queries and Python code for data analysis. Configure your MySQL database connection using the sidebar.")

if st.session_state.db_connected and st.session_state.db_config['DATABASE']:
    st.write(
        f"Using database: `{st.session_state.db_config['DATABASE']}` "
        f"at `{st.session_state.db_config['HOST']}:{st.session_state.db_config['PORT']}`"
    )
else:
    st.warning("Not connected. Provide credentials and click the button in the sidebar.")

if 'db_connection' not in st.session_state:
    st.session_state.db_connection = None
if 'agent_memory_sql' not in st.session_state:
    st.session_state.agent_memory_sql = None
if 'agent_memory_python' not in st.session_state:
    st.session_state.agent_memory_python = None
if 'connection_tested' not in st.session_state:
    st.session_state.connection_tested = False

def create_db_connection(config):
    """Create and return database connection"""
    try:
        connection_string = (
            f"mysql+pymysql://{config['USER']}:{config['PASSWORD']}@"
            f"{config['HOST']}:{config['PORT']}/{config['DATABASE']}"
        )
        engine = create_engine(connection_string, pool_pre_ping=True)
        db = SQLDatabase.from_uri(connection_string)
        return db
    except Exception as e:
        st.sidebar.error(f"Failed to create connection: {str(e)}")
        return None

def verify_connection():
    """Verify database connection is active"""
    if not st.session_state.get('db_config'):
        st.error("Database configuration not found")
        return False
    
    if not st.session_state.get('db_connection'):
        st.error("No active database connection")
        return False
        
    try:
        st.session_state.db_connection.run("SELECT 1")
        return True
    except:
        st.session_state.db_connection = create_db_connection(st.session_state.db_config)
        return st.session_state.db_connection is not None

def execute_query(query):
    """Execute query with connection verification"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        if verify_connection():
            try:
                result = st.session_state.db_connection.run(query)
                return result
            except exc.SQLAlchemyError as e:
                retry_count += 1
                if retry_count == max_retries:
                    st.error(f"Query failed after {max_retries} attempts: {str(e)}")
                    return None
                time.sleep(1)  # Wait before retry
        else:
            st.error("Connection verification failed")
            return None

warnings.filterwarnings("ignore")

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.join(current_dir, "..")
sys.path.insert(0, parent_dir)

os.environ['DEEPSEEK_API_KEY'] = DEEPSEEK_API_KEY


if 'messages' not in st.session_state:
    st.session_state.messages = []

if 'db_config' in st.session_state:
    if 'agent_memory_sql' not in st.session_state:
        st.session_state.agent_memory_sql = initialize_sql_agent(st.session_state.db_config)
    if 'agent_memory_python' not in st.session_state:
        st.session_state.agent_memory_python = initialize_python_agent()
    
    if 'sql_agent' not in st.session_state:
        st.session_state.sql_agent = st.session_state.agent_memory_sql
    if 'python_agent' not in st.session_state:
        st.session_state.python_agent = st.session_state.agent_memory_python
else:
    st.warning("Please configure database credentials first")


def generate_response(code_type, input_text):
    """Generate responses for both general and database-specific queries"""
    
    greetings = ['hello', 'hi', 'hey', 'help', 'what can you do']
    if input_text.lower() in greetings:
        return """Hello! I am a SQL and Python agent designed to help you with:SQL queries and database analysis, Python data visualization, and General database questions.To get started with database operations, please configure your database connection in the sidebar.You can also ask me general questions about SQL, Python, or data analysis!"""
    
    if not st.session_state.get('sql_agent'):
        return "Please configure and connect to a database using the sidebar before running queries."

    local_prompt = unidecode.unidecode(input_text)
    
    if code_type == "python":
        try:
            sql_response = st.session_state.sql_agent.invoke({"input": local_prompt})
            if not sql_response or 'output' not in sql_response:
                return "Failed to get SQL query results"
                
            local_response = sql_response['output']
            print("SQL Response->", local_response)
            
            exclusion_keywords = ["please provide", "don't know", "more context", 
                                "provide more", "vague request", "no results"]
            if any(keyword in local_response.lower() for keyword in exclusion_keywords):
                return "Unable to generate visualization - no valid data returned from query"
            
            viz_prompt = {"input": "Write code in python to plot the following data\n\n" + local_response}
            return st.session_state.python_agent.invoke(viz_prompt)
            
        except Exception as e:
            print(f"Error generating response: {str(e)}")
            return "Failed to generate visualization"
            
    else:  
        try:
            return st.session_state.sql_agent.run(local_prompt)
        except Exception as e:
            print(f"Full error details: {str(e)}")
            print(f"SQL query error: {str(e)}")
            return f"""Failed to execute SQL query. Details: {str(e)}"""


def reset_conversation():
    st.session_state.messages = []
    if 'db_config' in st.session_state:
        st.session_state.agent_memory_sql = initialize_sql_agent(st.session_state.db_config)
        st.session_state.agent_memory_python = initialize_python_agent()
        st.session_state.sql_agent = st.session_state.agent_memory_sql
        st.session_state.python_agent = st.session_state.agent_memory_python
    else:
        st.warning("Please configure database credentials first")

col1, col2 = st.columns([3, 1])
with col2:
    st.button("Reset Chat", on_click=reset_conversation)

for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="🚀" if message["role"] == "user" else "❇️"):
        if message["role"] in ("assistant", "error"):
            display_text_with_images(message["content"])
        elif message["role"] == "plot":
            exec(message["content"])
        else:
            st.markdown(message["content"])

if prompt := st.chat_input("Please ask your question:"):
    with st.chat_message("user", avatar="🚀"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    keywords = ["plot", "graph", "chart", "diagram", "visualize", "visualisation", "show"]
    if any(keyword in prompt.lower() for keyword in keywords):
        prev_context = ""
        for msg in reversed(st.session_state.messages):
            if msg["role"] == "assistant":
                prev_context = msg["content"] + "\n\n" + prev_context
                break
        if prev_context:
            prompt += f"\n\nGiven previous agent responses:\n{prev_context}\n"
        response = generate_response("python", prompt)
        if response == "NO_RESPONSE":
            response = "Please try again with a re-phrased query and more context"
            with st.chat_message("error"):
                display_text_with_images(response)
            st.session_state.messages.append({"role": "error", "content": response})
        else:
            code = display_code_plots(response['output'])
            try:
                code = f"import pandas as pd\n{code.replace('fig.show()', '')}"
                code += "st.plotly_chart(fig, theme='streamlit', use_container_width=True)"
                exec(code)
                st.session_state.messages.append({"role": "plot", "content": code})
            except:
                response = "Please try again with a re-phrased query and more context"
                with st.chat_message("error"):
                    display_text_with_images(response)
                st.session_state.messages.append({"role": "error", "content": response})
    else:
        if len(st.session_state.messages) > 1:
            context_length = 0
            prev_context = ""
            for msg in reversed(st.session_state.messages):
                if context_length > 1:
                    break
                if msg["role"] == "assistant":
                    prev_context = msg["content"] + "\n\n" + prev_context
                    context_length += 1
            response = generate_response("sql", f"{prompt}\n\nGiven previous agent responses:\n{prev_context}\n")
        else:
            response = generate_response("sql", prompt)
        with st.chat_message("assistant", avatar="❇️"):
            display_text_with_images(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

if 'query' not in st.session_state:
    st.session_state.query = ''

if 'query_input_key' not in st.session_state:
    st.session_state.query_input_key = 0