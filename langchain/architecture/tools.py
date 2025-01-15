from langchain_core.tools import tool # type: ignore

@tool
def multiply(a: int, b: int) -> int:
   """I can help with multiplying two numbers."""
   return a * b

response = multiply.invoke({"a": 2, "b": 3})
print(response)
print(multiply.name)
print(multiply.description)
print(multiply.args)