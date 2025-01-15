import getpass
import os
from langchain_openai import ChatOpenAI  


if not os.environ.get("OPENAI_API_KEY"):
  os.environ["OPENAI_API_KEY"] = getpass.getpass("Enter API key for OpenAI: ")

model = ChatOpenAI(model="gpt-4o-mini")
response = model.invoke("Hello, how are you?") 
print(response.content)

