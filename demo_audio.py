# chainlit run demo_audio.py -w --host 0.0.0.0 --port 8000
import chainlit as cl
from mcp import ClientSession
from openai import AsyncOpenAI
import os
import pdfplumber
from io import BytesIO
import asyncio
import numpy as np
import wave
import tempfile
from faster_whisper import WhisperModel
import edge_tts
import json

# === 语音识别配置 ===
WHISPER_MODEL = WhisperModel("small", device="cpu", compute_type="int8")  # 使用base模型更快

# === Setup DeepSeek API ===
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-a194d0c4c5364185ac916b8e19c65566")
if not DEEPSEEK_API_KEY:
    raise ValueError("plz setup DEEPSEEK_API_KEY")

client = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

settings = {
    "model": "deepseek-chat",
    "temperature": 0,
}

# Works for qwen3:8b
# client = AsyncOpenAI(
#     api_key="ollama",
#     base_url="http://10.86.30.146:11434/v1",
# )
# settings = {
#     "model": "qwen3:8b",
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

# === Audio Process ===
async def transcribe_audio(audio_data: bytes) -> str:
    """使用本地Whisper模型转录音频"""
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp_file:
        # 写入WAV文件
        with wave.open(tmp_file.name, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(audio_data)
        
        # 转录
        segments, _ = WHISPER_MODEL.transcribe(tmp_file.name, language="zh")
        return " ".join([seg.text for seg in segments])

async def text_to_speech(text: str) -> bytes:
    """使用edge-tts合成语音"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        tmp_path = tmp_file.name
    
    # 中文语音合成
    voice = "zh-CN-YunxiNeural"  # 微软云晓青年音
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(tmp_path)
    
    with open(tmp_path, "rb") as f:
        audio_data = f.read()
    os.unlink(tmp_path)
    return audio_data


MAX_HISTORY = 6  # Number of previous messages to keep

def get_chat_history():
    return cl.user_session.get("chat_history", [])

def add_to_chat_history(role: str, content: str):
    history = get_chat_history()
    history.append({"role": role, "content": content})
    # Keep only the latest N messages
    history = history[-MAX_HISTORY:]
    cl.user_session.set("chat_history", history)

# === 核心交互逻辑 ===
@cl.on_chat_start
async def start():
    cl.user_session.set("chat_history", [])
    cl.user_session.set("audio_chunks", [])

@cl.on_audio_start
async def on_audio_start():
    cl.user_session.set("audio_chunks", [])
    return True

@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.InputAudioChunk):
    audio_chunks = cl.user_session.get("audio_chunks")
    audio_chunks.append(chunk.data)
    cl.user_session.set("audio_chunks", audio_chunks)

@cl.on_audio_end
async def on_audio_end():
    if audio_chunks := cl.user_session.get("audio_chunks"):
        # 拼接音频数据
        audio_data = b"".join(audio_chunks)
        
        # 转录音频
        transcription = await transcribe_audio(audio_data)
        if not transcription:
            await cl.Message(content="❌ 未能识别语音").send()
            return
            
        # 显示用户语音输入（作为用户消息）
        user_msg = cl.Message(
            author="User",
            content=transcription,
            elements=[cl.Audio(mime="audio/wav", content=audio_data)]
        )
        await user_msg.send()
        
        # 调用LLM生成回复
        await generate_response(transcription)

async def generate_response(query: str) -> str:
    """使用DeepSeek生成回复，支持工具调用"""
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

    # Step 2: Build history + new message
    history = get_chat_history()
    history.append({"role": "user", "content": query})

    # Step 3: Prepare base messages
    base_messages = [
        {"role": "system", "content": "You are a helpful assistant of FUJIFILM Business Innovation, you will use the same language as user to answer the question, the newest chat history at last."}
    ] + history

    # Step 4: Send to LLM with or without tools
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

    # Step 5: If tools were used
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

        # Step 6: Summarize tool results into a final answer
        summary_prompt = f"""
        User Question:
        {query}

        Tool Results:
        """
        for output in tool_outputs:
            summary_prompt += f"\nTool: {output['name']}\nResult:\n{output['result']}\n"

        summary_prompt += """
        Instructions:
        1. Carefully read the tool outputs above.
        2. Use ONLY the information in the tool results to answer the user's question.
        3. Do NOT repeat tool results unless necessary — instead, directly answer the user.
        4. Write the answer in the same language used in the user's question.
        5. If the tool results are incomplete or unclear, politely indicate so.

        Answer:
        """
        summary_response = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers user questions using only the results from tools. Use the same language as the user."},
                {"role": "user", "content": summary_prompt}
            ],
            **settings
        )

        reply = summary_response.choices[0].message.content
        await cl.Message(content=f"🔍 Summary:\n{reply}").send()
    else:
        # No tool call, just use model response
        reply = msg.content
        await cl.Message(content=reply).send()

    # Store in history
    add_to_chat_history("assistant", reply)
    
    # 生成并播放语音回复
    audio_data = await text_to_speech(reply)
    await cl.Message(
        content="",
        elements=[cl.Audio(auto_play=True, mime="audio/wav", content=audio_data)]
    ).send()
    
    return reply

async def play_tts(text: str):
    """合成并播放语音"""
    audio_data = await text_to_speech(text)
    await cl.Message(
        content=text,
        elements=[cl.Audio(auto_play=True, mime="audio/wav", content=audio_data)]
    ).send()



# === Handle message and tools with LLM ===
@cl.on_message
async def on_message(message: cl.Message):
    # Step 1: Process PDF files if any
    pdf_content = ""
    if message.elements:
        pdf_files = [file for file in message.elements if file.mime == "application/pdf"]
        if pdf_files:
            try:
                for pdf_file in pdf_files:
                    with pdfplumber.open(pdf_file.path) as pdf:
                        text = ""
                        for page in pdf.pages:
                            text += page.extract_text() + "\n"
                        pdf_content += f"\n\nPDF Content:\n{text}\n"
            except Exception as e:
                await cl.Message(content=f"❌ Error reading PDF: {str(e)}").send()
                return

    # Step 2: Gather tools
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

    # Step 3: Build history + new message with PDF content if any
    history = get_chat_history()
    user_message = message.content
    if pdf_content:
        user_message += f"\n\nHere is the content of the attached PDF file(s):{pdf_content}"
    history.append({"role": "user", "content": user_message})

    # Step 4: Prepare base messages
    base_messages = [
        {"role": "system", "content": "You are a helpful assistant of FUJIFILM Business Innovation, you will use the same language as user to answer the question, the newest chat history at last."
        "If the user question requires analyzing a document, especially a PDF, "
        "say: '📝 Please upload a PDF file so I can help you.'"}
    ] + history

    # Step 5: Send to LLM with or without tools
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

    # # Store current messages to history
    # add_to_chat_history("user", message.content)
    # if msg.content:
    #     add_to_chat_history("assistant", msg.content)

    # Store current messages to history
    add_to_chat_history("user", user_message)
    if msg.content:
        add_to_chat_history("assistant", msg.content)

    # 🔍 Check if model is asking for a PDF
    if msg.content and "upload a pdf" in msg.content.lower():
        await cl.Message(content=msg.content).send()

        # Ask for file
        files = await cl.AskFileMessage(
            content="📄 Upload your PDF file here.",
            accept=["application/pdf"],
            max_files=1
        ).send()

        file = files[0]

        # Extract text from PDF using pdfminer
        from pdfminer.high_level import extract_text
        from io import BytesIO

        try:
            text = extract_text(file.path)
        except Exception as e:
            await cl.Message(content=f"❌ Could not read PDF: {e}").send()
            return

        # Optionally summarize or chunk text
        summary_prompt = f"The user uploaded the following document:\n\n{text}\n\nPlease summarize it or help based on the user's original request:\n\n{message.content}"
        print(summary_prompt)
        followup_response = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": summary_prompt}
            ],
            **settings
        )
        print(followup_response.choices[0].message.content)

        await cl.Message(content=followup_response.choices[0].message.content).send()
        return
    tool_outputs = []

    # Step 6: If tools were used
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

        # Step 7: Summarize tool results into a final answer
        summary_prompt = f"""
        User Question:
        {user_message}

        Tool Results:
        """
        for output in tool_outputs:
            summary_prompt += f"\nTool: {output['name']}\nResult:\n{output['result']}\n"

        summary_prompt += """
        Instructions:
        1. Carefully read the tool outputs above.
        2. Use ONLY the information in the tool results to answer the user's question.
        3. Do NOT repeat tool results unless necessary — instead, directly answer the user.
        4. Write the answer in the same language used in the user's question.
        5. If the tool results are incomplete or unclear, politely indicate so.

        Answer:
        """
        summary_response = await client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers user questions using only the results from tools. Use the same language as the user."},
                {"role": "user", "content": summary_prompt}
            ],
            **settings
        )

        await cl.Message(content=f"🔍 Summary:\n{summary_response.choices[0].message.content}").send()

    else:
        # No tool call, just send model response
        await cl.Message(content=msg.content).send()

