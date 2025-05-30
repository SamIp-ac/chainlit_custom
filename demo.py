
# chainlit run demo.py -w --host 0.0.0.0 --port 8000
import chainlit as cl
from mcp import ClientSession
from openai import AsyncOpenAI
import os

# === Setup DeepSeek API ===
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-your-api-key")
if not DEEPSEEK_API_KEY:
    raise ValueError("请设置 DEEPSEEK_API_KEY 环境变量。")

client = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

settings = {
    "model": "deepseek-chat",
    "temperature": 0,
}

# Works for qwen3:4b
# client = AsyncOpenAI(
#     api_key="ollama",
#     base_url="http://localhost:11434/v1",
# )
# settings = {
#     "model": "qwen3:4b",
#     "temperature": 0,
# } # Can not turn off reasoning: "chat_template_kwargs": {"enable_thinking": false}
# === Store MCP tool metadata ===

@cl.on_mcp_connect
async def on_mcp_connect(connection, session: ClientSession):
    result = await session.list_tools()
    tools = [{
        "name": t.name,
        "description": t.description,
        "input_schema": t.inputSchema,
    } for t in result.tools]
    
    mcp_tools = cl.user_session.get("mcp_tools", {})
    mcp_tools[connection.name] = tools
    cl.user_session.set("mcp_tools", mcp_tools)

@cl.on_mcp_disconnect
async def on_mcp_disconnect(name: str, session: ClientSession):
    mcp_tools = cl.user_session.get("mcp_tools", {})
    if name in mcp_tools:
        del mcp_tools[name]
    cl.user_session.set("mcp_tools", mcp_tools)

# === Helper to find MCP for a tool ===
def find_mcp_for_tool(tool_name):
    mcp_tools = cl.user_session.get("mcp_tools", {})
    for mcp_name, tools in mcp_tools.items():
        if any(tool["name"] == tool_name for tool in tools):
            return mcp_name
    raise ValueError(f"No MCP connection found for tool '{tool_name}'")

# === Call tool by name ===
import json

@cl.step(type="tool")
async def call_tool(tool_use):
    tool_name = tool_use["name"]
    tool_input = tool_use["input"]

    # Convert string input to dict if necessary
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except Exception as e:
            raise ValueError(f"Invalid JSON string for tool input: {tool_input}") from e

    mcp_name = find_mcp_for_tool(tool_name)
    mcp_session, _ = cl.context.session.mcp_sessions.get(mcp_name)

    result = await mcp_session.call_tool(tool_name, tool_input)
    return result


# === Handle message and tools with LLM ===
@cl.on_message
async def on_message(message: cl.Message):
    # Step 1: Gather tools
    mcp_tools = cl.user_session.get("mcp_tools", {})
    tool_defs = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"]
            }
        }
        for conn_tools in mcp_tools.values() for t in conn_tools
    ]

    # Step 2: Prepare base messages
    base_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": message.content}
    ]

    # Step 3: Send to LLM with or without tools
    if tool_defs:
        response = await client.chat.completions.create(
            messages=base_messages,
            tools=tool_defs,
            tool_choice="auto",
            **settings
        )
    else:
        response = await client.chat.completions.create(
            messages=base_messages,
            **settings
        )

    msg = response.choices[0].message
    tool_outputs = []

    # Step 4: If tools were used
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            tool_use = {
                "name": tool_call.function.name,
                "input": tool_call.function.arguments
            }
            result = await call_tool(tool_use)

            # Extract result
            if isinstance(result, dict) and "content" in result:
                content_items = result["content"]
                if isinstance(content_items, list) and len(content_items) > 0:
                    result_text = content_items[0].text
                else:
                    result_text = str(result)
            else:
                result_text = str(result)

            tool_outputs.append({
                "name": tool_use["name"],
                "result": result_text
            })

            await cl.Message(content=f"Tool `{tool_use['name']}` response:\n```json\n{result_text}\n```").send()

        # Step 5: Summarize tool results
        summary_prompt = "Here are the results from tools:\n"
        for output in tool_outputs:
            summary_prompt += f"\nTool: {output['name']}\nResult:\n{output['result']}\n"
        summary_prompt += "\nPlease summarize the relevant findings or answer the user's original question based on this."

        summary_response = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes tool outputs."},
                {"role": "user", "content": summary_prompt}
            ],
            **settings
        )

        await cl.Message(content=f"🔍 Summary:\n{summary_response.choices[0].message.content}").send()

    else:
        # No tool call, just send model response
        await cl.Message(content=msg.content).send()
