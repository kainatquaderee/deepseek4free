"""
DeepSeek MCP Server - Exposes DeepSeek R1 as a tool for Qwen Code

This server allows Qwen Code to use DeepSeek as an external reasoning engine
via the MCP (Model Context Protocol).
"""

from mcp.server.fastmcp import FastMCP
from dsk.api import DeepSeekAPI
import os
import time

# Initialize MCP server
mcp = FastMCP("DeepSeek-Brain")

# Initialize DeepSeek API
# Make sure DEEPSEEK_AUTH_TOKEN is set in .env file
auth_token = os.getenv("DEEPSEEK_AUTH_TOKEN")
if not auth_token:
    raise ValueError("DEEPSEEK_AUTH_TOKEN environment variable is not set")

api = DeepSeekAPI(auth_token)

# Track active chat sessions
# Structure: {session_key: {"chat_id": str, "file_content": str | None}}
active_sessions = {}

# Store message IDs for conversation continuity
conversation_state = {}


@mcp.tool()
async def ask_deepseek_reasoner(prompt: str, use_thinking: bool = True, use_search: bool = False) -> str:
    """
    Ask DeepSeek R1 for deep analysis and reasoning (one-off, session not kept).
    """
    chat_id = api.create_chat_session()
    try:
        response = ""
        for chunk in api.chat_completion(chat_id, prompt, thinking_enabled=use_thinking, search_enabled=use_search):
            if chunk['type'] == 'text':
                response += chunk['content']
        api.delete_chat_session(chat_id)
        return response
    except Exception as e:
        if chat_id:
            try:
                api.delete_chat_session(chat_id)
            except:
                pass
        raise Exception(f"DeepSeek API error: {str(e)}")


@mcp.tool()
async def analyze_code_with_deepseek(code: str, task_description: str = "") -> str:
    """Analyze code and provide insights."""
    prompt = f"Analyze this code and provide detailed feedback"
    if task_description:
        prompt += f" for: {task_description}"
    prompt += f"\n\nCode:\n```python\n{code}\n```"
    
    chat_id = api.create_chat_session()
    try:
        response = ""
        for chunk in api.chat_completion(chat_id, prompt, thinking_enabled=True):
            if chunk['type'] == 'text':
                response += chunk['content']
        api.delete_chat_session(chat_id)
        return response
    except Exception as e:
        if chat_id:
            try:
                api.delete_chat_session(chat_id)
            except:
                pass
        raise Exception(f"DeepSeek API error: {str(e)}")


@mcp.tool()
async def upload_file_to_deepseek(file_path: str) -> str:
    """
    Read a file and prepare it for analysis.
    Content is stored in memory for use in subsequent tool calls.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return f"File loaded: {os.path.basename(file_path)} ({len(content)} chars). Use ask_deepseek_with_file to analyze."
    except Exception as e:
        raise Exception(f"File error: {str(e)}")


@mcp.tool()
async def ask_deepseek_with_file(file_path: str, prompt: str, use_thinking: bool = True) -> str:
    """
    Analyze a file by sending its content to DeepSeek.
    Session is kept alive for follow-up questions.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
    except Exception as e:
        raise Exception(f"Could not read file: {str(e)}")

    chat_id = api.create_chat_session()
    session_key = f"session_{int(time.time())}"
    active_sessions[session_key] = {"chat_id": chat_id, "file_content": file_content, "file_path": file_path}

    try:
        full_prompt = f"Here is the file content:\n\n```\n{file_content}\n```\n\n{prompt}"
        response = ""
        for chunk in api.chat_completion(chat_id, full_prompt, thinking_enabled=use_thinking):
            if chunk['type'] == 'text':
                response += chunk['content']
        return response
    except Exception as e:
        if chat_id:
            try:
                api.delete_chat_session(chat_id)
            except:
                pass
        if session_key in active_sessions:
            del active_sessions[session_key]
        raise Exception(f"DeepSeek API error: {str(e)}")


@mcp.tool()
async def create_session_with_file(file_path: str) -> str:
    """
    Create a persistent chat session with a file's content loaded.
    Use ask_in_session_with_file for follow-up questions.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        chat_id = api.create_chat_session()
        session_key = f"session_{int(time.time())}"
        active_sessions[session_key] = {
            "chat_id": chat_id,
            "file_content": file_content,
            "file_path": file_path
        }
        return f"Session created with file. Session ID: {chat_id} (key: {session_key})"
    except Exception as e:
        raise Exception(f"Session creation error: {str(e)}")


@mcp.tool()
async def ask_in_session_with_file(session_key: str, prompt: str, use_thinking: bool = True) -> str:
    """
    Ask a question in an existing session that has a file loaded.
    Maintains conversation context across multiple questions.
    """
    if session_key not in active_sessions:
        raise Exception(f"Session '{session_key}' not found.")

    session_data = active_sessions[session_key]
    chat_id = session_data["chat_id"]
    file_content = session_data.get("file_content")
    last_message_id = conversation_state.get(chat_id, {}).get("last_message_id")

    try:
        # Include file content if first message or explicitly asked
        if file_content and (last_message_id is None or "file" in prompt.lower() or "content" in prompt.lower()):
            full_prompt = f"Here is the file content:\n\n```\n{file_content}\n```\n\n{prompt}"
        else:
            full_prompt = prompt
        
        response = ""
        for chunk in api.chat_completion(chat_id, full_prompt, parent_message_id=last_message_id, thinking_enabled=use_thinking):
            if chunk['type'] == 'text':
                response += chunk['content']
            if 'message_id' in chunk:
                if chat_id not in conversation_state:
                    conversation_state[chat_id] = {}
                conversation_state[chat_id]["last_message_id"] = chunk['message_id']
        return response
    except Exception as e:
        raise Exception(f"DeepSeek API error: {str(e)}")


@mcp.tool()
async def create_deepseek_session() -> str:
    """Create a new persistent chat session."""
    try:
        chat_id = api.create_chat_session()
        session_key = f"session_{int(time.time())}"
        active_sessions[session_key] = chat_id
        return f"Session created. Session ID: {chat_id} (key: {session_key})"
    except Exception as e:
        raise Exception(f"Session creation error: {str(e)}")


@mcp.tool()
async def delete_deepseek_session(session_id: str) -> str:
    """Delete a DeepSeek chat session."""
    try:
        result = api.delete_chat_session(session_id)
        for key, value in list(active_sessions.items()):
            if value == session_id or (isinstance(value, dict) and value.get("chat_id") == session_id):
                del active_sessions[key]
        return result
    except Exception as e:
        raise Exception(f"Session deletion error: {str(e)}")


@mcp.tool()
async def list_deepseek_sessions() -> str:
    """List all active chat sessions."""
    if not active_sessions:
        return "No active sessions"
    
    sessions_list = []
    for key, value in active_sessions.items():
        if isinstance(value, dict):
            chat_id = value["chat_id"]
        else:
            chat_id = value
        sessions_list.append(f"  {key}: {chat_id}")
    
    return f"Active sessions:\n" + "\n".join(sessions_list)


@mcp.tool()
async def ask_deepseek_in_session(session_key: str, prompt: str, use_thinking: bool = True, use_search: bool = False) -> str:
    """
    Send a message to an existing chat session and continue the conversation.
    """
    if session_key not in active_sessions:
        raise Exception(f"Session '{session_key}' not found.")

    session_data = active_sessions[session_key]
    chat_id = session_data["chat_id"] if isinstance(session_data, dict) else session_data
    last_message_id = conversation_state.get(chat_id, {}).get("last_message_id")

    try:
        response = ""
        for chunk in api.chat_completion(chat_id, prompt, parent_message_id=last_message_id, thinking_enabled=use_thinking, search_enabled=use_search):
            if chunk['type'] == 'text':
                response += chunk['content']
            if 'message_id' in chunk:
                if chat_id not in conversation_state:
                    conversation_state[chat_id] = {}
                conversation_state[chat_id]["last_message_id"] = chunk['message_id']
        return response
    except Exception as e:
        raise Exception(f"DeepSeek API error: {str(e)}")


@mcp.tool()
async def continue_deepseek_conversation(session_key: str, prompt: str, use_thinking: bool = True) -> str:
    """Continue a conversation (convenience wrapper)."""
    return await ask_deepseek_in_session(session_key, prompt, use_thinking, use_search=False)


@mcp.tool()
async def get_session_info(session_key: str) -> str:
    """Get information about a specific session."""
    if session_key not in active_sessions:
        return f"Session '{session_key}' not found."

    session_data = active_sessions[session_key]
    chat_id = session_data["chat_id"] if isinstance(session_data, dict) else session_data
    last_message_id = conversation_state.get(chat_id, {}).get("last_message_id", "None")

    return f"Session: {session_key}\nChat ID: {chat_id}\nLast Message ID: {last_message_id}"


if __name__ == "__main__":
    mcp.run()
