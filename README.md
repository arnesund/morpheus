# Morpheus

My personal AI assistant overlord, designed to help with task management.

## Dependencies

 * OpenAI API key for the AI model.
 * Slack workspace where you can add a bot and create channels for various purposes.

## Environment variables

Example .env file, all of these variables are currently required:
```
OPENAI_API_KEY="sk-..."
SLACK_APP_TOKEN="xapp-..."
SLACK_BOT_TOKEN="xoxb-..."
SLACK_SIGNING_SECRET="..."
MORPHEUS_CHANNEL_ID=""
TASKS_CHANNEL_ID=""
WORK_TASKS_CHANNEL_ID=""
DENO_PATH=""
```

## Installing required dependencies for the MCP Run Python server

The server uses deno so make sure to install that first: https://docs.deno.com/runtime/

Run the following command to get dependencies for the Run Python server:
```
deno run -N -R=node_modules -W=node_modules --node-modules-dir=auto jsr:@pydantic/mcp-run-python warmup
```

## How to run

Use `uv` like this:
```
uv run python morpheus.py
```

The assistant creates two subfolders "logs" and "notes", as well as SQLite databases in the current directory to keep track of tasks.

## Personalization

If you want to personalize Morpheus, you can create a `system_prompt.md` file in the same directory as `morpheus.py`. The contents of this file will be used as the system prompt for the AI model.
