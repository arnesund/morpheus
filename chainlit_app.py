import asyncio
import os
import logging
from logging.handlers import TimedRotatingFileHandler
from dotenv import load_dotenv
import chainlit as cl

from agent import MorpheusBot

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

os.makedirs("logs", exist_ok=True)

file_handler = TimedRotatingFileHandler("logs/chainlit.log", when="midnight", interval=1)
file_handler.suffix = "%Y-%m-%d"
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%d-%b-%y %H:%M:%S"))
logger.addHandler(file_handler)

load_dotenv()

required_vars = ["OPENAI_API_KEY", "DENO_PATH"]
missing_vars = [var for var in required_vars if not os.getenv(var)]

system_prompt = ""
system_prompt_filepath = "system_prompt.md"
if os.path.exists(system_prompt_filepath):
    with open(system_prompt_filepath, "r", encoding="utf-8") as file:
        system_prompt = file.read()

morpheus_bot = None
if not missing_vars:
    try:
        morpheus_bot = MorpheusBot(system_prompt=system_prompt, notebook_filename="notebook.md")
        logger.info("MorpheusBot initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing MorpheusBot: {e}")
else:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")

@cl.on_chat_start
async def on_chat_start():
    """Initialize the chat session when a new user connects."""
    if morpheus_bot:
        cl.user_session.set("bot", morpheus_bot)
        
        clear_action = cl.Action(name="clear_chat", label="Clear Chat", description="Clear the conversation history", payload={})
        await cl.Message(
            content="Welcome! I'm Morpheus, your task management assistant. How can I help you today?",
            actions=[clear_action]
        ).send()
    else:
        missing_env_vars = ", ".join(missing_vars)
        await cl.Message(
            content=f"⚠️ **Configuration Error**: Missing required environment variables: {missing_env_vars}. Please set these variables in your .env file and restart the application."
        ).send()

@cl.action_callback("clear_chat")
async def clear_chat_callback(action):
    """Reset the conversation history when the Clear Chat action is triggered."""
    bot = cl.user_session.get("bot")
    if bot:
        bot.history = []
        bot.history_timestamp = None
        await cl.Message(content="Conversation history has been cleared. Let's start fresh!").send()
    else:
        await cl.Message(content="⚠️ Bot is not properly initialized. Please check your environment configuration.").send()

@cl.on_message
async def on_message(message: cl.Message):
    """Process a message from the user and generate a response."""
    bot = cl.user_session.get("bot")
    
    if not bot:
        missing_env_vars = ", ".join(missing_vars)
        await cl.Message(
            content=f"⚠️ **Configuration Error**: Bot is not initialized. Missing required environment variables: {missing_env_vars}. Please set these variables in your .env file and restart the application."
        ).send()
        return
    
    try:
        result_msg = cl.Message(content="")
        
        async with bot.agent.run_mcp_servers():
            with cl.Step(name="Processing request") as step:
                result = await bot.agent.run(message.content, message_history=bot.get_history())
                
                bot.log_messages(result, bot.history)
                bot.set_history(result.all_messages())
                
                intermediate_content = ""
                final_content = ""
                tool_calls = []
                
                messages = result.new_messages()
                
                for i, msg in enumerate(messages):
                    is_final_message = (i == len(messages) - 1)
                    message_content = ""
                    
                    for part in msg.parts:
                        if hasattr(part, 'has_content') and part.has_content():
                            if hasattr(part, 'tool_name'):  # For ToolCallPart
                                tool_call_content = {
                                    "tool": part.tool_name,
                                    "args": part.args if hasattr(part, 'args') else {},
                                    "result": part.content if hasattr(part, 'content') else ""
                                }
                                tool_calls.append(tool_call_content)
                                
                                message_content += f"\n\nTool Call: {part.tool_name}\n"
                                if hasattr(part, 'content') and part.content:
                                    message_content += f"Result: {part.content}\n"
                            else:  # For TextPart
                                message_content += part.content
                    
                    if is_final_message:
                        final_content = message_content
                    else:
                        intermediate_content += message_content
                
                step.output = intermediate_content
        
        await cl.Message(content=final_content).send()
        
    except Exception as e:
        logger.exception(f"Error processing message: {e}")
        await cl.Message(content=f"I encountered an error while processing your request. Please try again or contact support if the issue persists.").send()
