import os
import json
import openai
import asyncio
import logging
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
)

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# Initialize Bolt app
app = App(token = SLACK_BOT_TOKEN, signing_secret = SLACK_SIGNING_SECRET)
socket_mode_handler = SocketModeHandler(app, SLACK_BOT_TOKEN)
client = WebClient(os.environ["SLACK_BOT_TOKEN"])

# Initialize OpenAI API
openai.api_key = os.environ.get("OPENAI_API_KEY")

# Define function to write messages to JSON file
def write_to_file(message):
    with open("messages.json", "a") as f:
        json.dump(message, f)
        f.write("\n")

# Define function to handle @Morpheus mentions
@app.event("app_mention")
async def handle_mention(body, say, client):
    channel_id = body["event"]["channel"]
    user_message = body["event"]["text"]
    
    # Read messages from file
    with open("messages.json", "r") as file:
        messages = file.readlines()
    
#    # Initialize OpenAI Chat API request
#    response = openai.ChatCompletion.create(
#        model="text-davinci-003",
#        messages=[{"role": "system", "content": message} for message in messages],
#        max_tokens=100,
#        prompt=user_message
#    )
    
    # Post response to Slack channel
#    try:
#        say(response.choices[0].text.strip())
#    except SlackApiError as e:
#        print(f"Error posting message: {e.response['error']}")


# Define function to listen for messages in "#tasks" channel
@app.event("message")
async def handle_message(body, say, client):
    channel_id = body["event"]["channel"]
    message_text = body["event"]["text"]
    
    # Write message to file if it's in the #tasks channel
    #if channel_id == "tasks":
    write_to_file(message_text)

if __name__ == "__main__":
    auth_test = client.auth_test()
    socket_mode_handler.connect()
    logging.info(f"Connected as {auth_test['app_name']}")
    loop = asyncio.get_event_loop()
    loop.create_task()  # TODO
    loop.run_forever()
