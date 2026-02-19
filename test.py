import openai
import json

API_KEY = "sk-CampR5GL-yySBHH4Agm2Sw"

client = openai.OpenAI(
    api_key=API_KEY,
    base_url="https://ete-litellm.ai-models.vpc-int.res.ibm.com" # LiteLLM Proxy is OpenAI compatible, Read More: https://docs.litellm.ai/docs/proxy/user_keys
)

# Define tools the agent can use
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to read"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            }
        }
    }
]

def execute_tool(name: str, args: dict) -> str:
    """Execute a tool and return the result."""
    if name == "search_web":
        return f"Search results for '{args['query']}': [mock results]"
    elif name == "read_file":
        try:
            with open(args["path"]) as f:
                return f.read()
        except Exception as e:
            return f"Error: {e}"
    elif name == "write_file":
        try:
            with open(args["path"], "w") as f:
                f.write(args["content"])
            return f"Successfully wrote to {args['path']}"
        except Exception as e:
            return f"Error: {e}"
    return "Unknown tool"

def run_agent(task: str, max_iterations: int = 10):
    """Run an agentic loop until task completion."""
    messages = [
        {
            "role": "system",
            "content": """You are an autonomous agent that completes tasks step
by step.

Think through problems carefully. Use tools when needed. When the task is
complete,
respond with DONE: followed by a summary of what you accomplished."""
        },
        {"role": "user", "content": task}
    ]

    for i in range(max_iterations):
        print(f"\n--- Iteration {i + 1} ---")

        response = client.chat.completions.create(
            model="aws/claude-opus-4-5",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        message = response.choices[0].message
        messages.append(message)

        # Check if agent is done
        if message.content and message.content.startswith("DONE:"):
            print(f"Agent completed: {message.content}")
            return message.content

        # Handle tool calls
        if message.tool_calls:
            for tool_call in message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                print(f"Calling {name}({args})")

                result = execute_tool(name, args)
                print(f"Result: {result[:200]}...")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
        elif message.content:
            print(f"Agent: {message.content}")

    return "Max iterations reached"

# Run the agent
if __name__ == "__main__":
    result = run_agent("Research what Python version is latest and create a summary.txt file")
    print(f"\nFinal result: {result}")