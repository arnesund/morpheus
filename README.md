# Morpheus

My personal AI assistant overlord, designed to help with task management. Can be used as a Slackbot or in the web UI.

## Dependencies

 * OpenAI API key for the AI model.
 * Slack workspace where you can add a bot and create channels for various purposes.

## Installing required dependencies for the MCP Run Python server

The server uses deno so make sure to install that first: https://docs.deno.com/runtime/

Run the following command to get dependencies for the Run Python server:
```
deno run -N -R=node_modules -W=node_modules --node-modules-dir=auto jsr:@pydantic/mcp-run-python warmup
```

## Environment variables

Example .env file, all of these variables are currently required:
```
OPENAI_API_KEY="sk-..."
SLACK_APP_TOKEN="xapp-..."
SLACK_BOT_TOKEN="xoxb-..."
SLACK_SIGNING_SECRET="..."
DENO_PATH=""
```

## How to run the Slackbot

Use `uv` like this:
```
uv run python morpheus.py --channel <SLACK CHANNEL ID>
```

The assistant creates two subfolders "logs" and "notes", as well as SQLite databases in the current directory to keep track of tasks.

## Personalization

If you want to personalize Morpheus, you can create a `system_prompt.md` file and pass the path to it as an argument. The contents of this file will be used as the system prompt for the AI model.

Specify the path to the system prompt file like this:
```
uv run python morpheus.py --channel <SLACK_CHANNEL_ID> --system-prompt system_prompt.md
```

## How to run the web UI

The web UI is built using Chainlit. Start it up like this:
```
uv run chainlit run chainlit_app.py --host 0.0.0.0
```

## Running tests

The project uses pytest for testing. To run the tests:

```
# Create virtual environment and install test dependencies
uv venv
. .venv/bin/activate
uv pip install -e .
uv pip install pytest pytest-cov pytest-asyncio pytest-mock

# Run all tests
pytest

# Run tests with coverage report
pytest --cov=. --cov-report=term

# Run specific test categories
pytest tests/unit/
pytest tests/integration/

# Run tests with verbose output
pytest -v
```
