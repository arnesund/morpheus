import os
import json
import asyncio
import logging
from dotenv import load_dotenv
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_sdk.errors import SlackApiError
from agent import MorpheusBot  # Import the MorpheusBot class

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
)

# Environment variables for Slack tokens and channel IDs.
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")      # Bot token (xoxb-...)
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")      # App-level token (xapp-...)
TASKS_CHANNEL_ID = os.getenv("TASKS_CHANNEL_ID")    # Channel ID for "#tasks"
MORPHEUS_CHANNEL_ID = os.getenv("MORPHEUS_CHANNEL_ID")  # Channel ID for "#morpheus"

# Instantiate the MorpheusBot which initializes OpenAI, the SQLite database, and the agent.
bot = MorpheusBot()

# Initialize the Slack Bolt asynchronous app using the bot token.
app = AsyncApp(token=SLACK_BOT_TOKEN)

def write_to_file(message):
    with open("messages.json", "a") as f:
        json.dump(message, f)
        f.write("\n")

# Handle @Morpheus mentions.
@app.event("app_mention")
async def handle_mention(body, say):
    event = body.get("event", {})
    channel_id = event.get("channel")
    user_message = event.get("text", "")
    logging.debug(f"Received an @Morpheus mention in channel {channel_id}: {user_message}")

    # Use the process_message() wrapper to process the message and update history.
    result = await bot.process_message(user_message)
    response_text = result.data  # Agent's response

    await say(response_text)

# Listen for plain messages in designated channels (#tasks and #morpheus).
@app.event("message")
async def handle_message(body, say):
    event = body.get("event", {})
    channel_id = event.get("channel")
    message_text = event.get("text", "")

    # Check if the message is coming from a channel where Morpheus should respond.
    if channel_id == TASKS_CHANNEL_ID or channel_id == MORPHEUS_CHANNEL_ID:
        logging.debug(f"Received message in channel {channel_id}: {message_text}")

        # Optionally log messages from the #tasks channel.
        if channel_id == TASKS_CHANNEL_ID:
            write_to_file({"channel": channel_id, "text": message_text})
        
        # Process the message using our wrapper method.
        result = await bot.process_message(message_text)
        response_text = result.data

        try:
            await say(response_text)
        except SlackApiError as e:
            logging.error(f"Failed to post message: {e}")

# Main entry point to start the Socket Mode handler.
async def main():
    socket_mode_handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)
    auth_test = await app.client.auth_test()
    logging.info(f"Connected as {auth_test.get('user')}")
    await socket_mode_handler.start_async()

if __name__ == "__main__":
    asyncio.run(main())
