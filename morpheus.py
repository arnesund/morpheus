import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from logging.handlers import TimedRotatingFileHandler

from dotenv import load_dotenv
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_sdk.errors import SlackApiError

from agent import MorpheusBot

load_dotenv()

os.makedirs("logs", exist_ok=True)

# Set up logging to both stdout and a file with daily rotation.
logger = logging.getLogger()
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler(sys.stdout)
file_handler = TimedRotatingFileHandler(
    "logs/morpheus.log", when="midnight", interval=1
)
file_handler.suffix = "%Y-%m-%d"

formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s", datefmt="%d-%b-%y %H:%M:%S"
)
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Environment variables for Slack tokens and channel IDs.
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")  # Bot token (xoxb-...)
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")  # App-level token (xapp-...)
TASKS_CHANNEL_ID = os.getenv("TASKS_CHANNEL_ID")  # Channel ID for "#tasks"
MORPHEUS_CHANNEL_ID = os.getenv("MORPHEUS_CHANNEL_ID")  # Channel ID for "#morpheus"
WORK_TASKS_CHANNEL_ID = os.getenv(
    "WORK_TASKS_CHANNEL_ID"
)  # Channel ID for "#worktasks"


def parse_arguments():
    """
    Parse command line arguments for channel ID, notebook path, and task database path.
    Returns default values if arguments are not provided.
    """
    parser = argparse.ArgumentParser(
        description="Start Morpheus Slackbot for a single channel"
    )
    parser.add_argument(
        "--channel",
        help="Slack channel ID to listen to (defaults to MORPHEUS_CHANNEL_ID env var)",
        default=MORPHEUS_CHANNEL_ID,
    )
    parser.add_argument(
        "--notebook",
        help="Path to notebook file (defaults to notebook.md)",
        default="notebook.md",
    )
    parser.add_argument(
        "--db",
        help="Path to task database file (defaults to tasks.db)",
        default="tasks.db",
    )
    return parser.parse_args()


# Use the contents of "system_prompt.md" as system prompt, if it exists
system_prompt = ""
system_prompt_filepath = "system_prompt.md"
if os.path.exists(system_prompt_filepath):
    with open(system_prompt_filepath, "r", encoding="utf-8") as file:
        system_prompt = file.read()
# Read in a translated version if exists
system_prompt_nb_filepath = "system_prompt_nb.md"
if os.path.exists(system_prompt_nb_filepath):
    with open(system_prompt_nb_filepath, "r", encoding="utf-8") as file:
        system_prompt_nb = file.read()

# Parse command line arguments
args = parse_arguments()

if not args.channel:
    logger.error(
        "No channel ID provided. Use --channel argument or set MORPHEUS_CHANNEL_ID environment variable."
    )
    sys.exit(1)

bot = MorpheusBot(
    db_filename=args.db, system_prompt=system_prompt, notebook_filename=args.notebook
)

# Initialize the Slack Bolt asynchronous app using the bot token.
app = AsyncApp(token=SLACK_BOT_TOKEN)


def select_bot(channel_id: str) -> MorpheusBot:
    """
    Returns the bot instance if the channel ID matches the configured channel.
    This is a simplified version of the previous select_bot function
    that handled multiple channels.
    """
    return bot


# Listen for plain messages in the specified channel.
@app.event("message")
async def handle_message(body, say):
    event = body.get("event", {})
    channel_id = event.get("channel")
    message_text = event.get("text", "")

    # Only process messages in the specified channel.
    if channel_id == args.channel:
        logger.debug(f"Received message in channel {channel_id}: {message_text}")
        # Log the message for debugging/information purposes.
        logger.info(f"Channel: {channel_id} | Message: {message_text}")
        # Process the message using the bot's process_message() wrapper.
        slack_message_dict = await bot.process_message(message_text)
        try:
            await say(slack_message_dict)
        except SlackApiError as e:
            logger.error(f"Failed to post message: {e}")


# Main entry point to start the Socket Mode handler.
async def main():
    socket_mode_handler = AsyncSocketModeHandler(app, SLACK_APP_TOKEN)

    try:
        auth_test = await app.client.auth_test()
        logger.info(f"Connected as {auth_test.get('user')}")
        await socket_mode_handler.start_async()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, shutting down gracefully...")
    finally:
        await socket_mode_handler.client.close()
        logger.info("Application shut down successfully.")


if __name__ == "__main__":
    try:
        logger.info(
            f"Starting Morpheus bot for channel {args.channel} with notebook {args.notebook} and database {args.db}"
        )
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
    except Exception as e:
        logger.exception(f"Unhandled exception")
