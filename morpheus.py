import os
import json
import asyncio
import logging
from dotenv import load_dotenv
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_sdk.errors import SlackApiError
from pydantic_ai import Agent

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
)

# Environment variables
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")      # Bot token (xoxb-...)
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")      # App-level token (xapp-...)
TASKS_CHANNEL_ID = os.getenv("TASKS_CHANNEL_ID")    # Channel ID for the "#tasks" channel

# Initialize the Slack Bolt asynchronous app using the bot token.
app = AsyncApp(token=SLACK_BOT_TOKEN)

# Initialize the Pydantic AI agent (using GPT-4o)
agent = Agent('openai:gpt-4o')

def write_to_file(message):
    with open("messages.json", "a") as f:
        json.dump(message, f)
        f.write("\n")

# Handle @Morpheus mentions
@app.event("app_mention")
async def handle_mention(body, say):
    event = body.get("event", {})
    channel_id = event.get("channel")
    user_message = event.get("text", "")
    logging.debug(f"Received an @Morpheus mention in channel {channel_id}: {user_message}")

    # Process the message using the Pydantic AI agent
    result = await agent.run(user_message)
    response_text = result.data  # Agent's response

    # Respond back in Slack using the bot token.
    await say(response_text)

# Listen for messages in the designated "#tasks" channel
@app.event("message")
async def handle_message(body, say):
    event = body.get("event", {})
    channel_id = event.get("channel")
    message_text = event.get("text", "")

    # Only process messages from the designated #tasks channel
    if channel_id == TASKS_CHANNEL_ID:
        logging.debug(f"Received message in #tasks channel: {message_text}")
        write_to_file({"channel": channel_id, "text": message_text})

        result = await agent.run(message_text)
        response_text = result.data

        try:
            await say(response_text)
        except SlackApiError as e:
            logging.error(f"Failed to post message: {e}")

# Main entry point to start the Socket Mode handler.
async def main():
    # Instantiate the AsyncSocketModeHandler using the app-level token.
    socket_mode_handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)

    # Test authentication and log the connected user.
    auth_test = await app.client.auth_test()
    logging.info(f"Connected as {auth_test.get('user')}")

    # Start the Socket Mode handler to listen for events.
    await socket_mode_handler.start_async()

if __name__ == "__main__":
    asyncio.run(main())
