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

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
TASKS_CHANNEL_ID = os.getenv("TASKS_CHANNEL_ID")  # Set this to your "#tasks" channel ID

# Initialize Slack Bolt asynchronous app
app = AsyncApp(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)
socket_mode_handler = AsyncSocketModeHandler(app, SLACK_BOT_TOKEN)

# Initialize the Pydantic AI agent (using GPT-4o)
agent = Agent('openai:gpt-4o')

# Define a function to write messages to a JSON file for logging purposes
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

    # Process the message asynchronously with the agent
    result = await agent.run(user_message)
    response_text = result.data  # This contains agent's response

    # Post the agent's response back to Slack
    await say(response_text)

# Listen for messages specifically in the "#tasks" channel
@app.event("message")
async def handle_message(body, say):
    event = body.get("event", {})
    channel_id = event.get("channel")
    message_text = event.get("text", "")

    # Only process messages from the designated #tasks channel
    if channel_id == TASKS_CHANNEL_ID:
        logging.debug(f"Received message in #tasks channel: {message_text}")
        # Write the message to file for logging
        write_to_file({"channel": channel_id, "text": message_text})

        # Process the message with the agent
        result = await agent.run(message_text)
        response_text = result.data

        try:
            # Post the result of the agent's processing back to the #tasks channel
            await say(response_text)
        except SlackApiError as e:
            logging.error(f"Failed to post message: {e}")

# Main entry point to start the Socket Mode connection
if __name__ == "__main__":
    async def main():
        # Check authentication and log the connected user
        auth_test = await app.client.auth_test()
        logging.info(f"Connected as {auth_test.get('user')}")

        # Start the app in Socket Mode
        await socket_mode_handler.start_async()

    asyncio.run(main())
