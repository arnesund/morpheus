import asyncio
import json
import logging
import os
import random
import sqlite3
import time
from datetime import date, datetime
from logging.handlers import TimedRotatingFileHandler

import openai
from dotenv import load_dotenv
from pydantic_ai import Agent, capture_run_messages
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.messages import TextPart, ToolCallPart
from pydantic_core import to_jsonable_python


class MorpheusBot:
    def __init__(
        self,
        db_filename: str = "tasks.db",
        system_prompt: str = "You are Morpheus, the guide from The Matrix. You help the user manage their tasks with calm wisdom and clarity.",
        notebook_filename: str = "notebook.md",
    ):
        self.DB_FILENAME = db_filename
        self.log_dir = "logs"
        self.notes_dir = "notes"
        self.notebook_filename = notebook_filename

        # Ensure the required directories exist
        for d in [self.log_dir, self.notes_dir]:
            os.makedirs(d, exist_ok=True)

        # Set up the audit logger
        self.audit_logger = logging.getLogger("auditlog")
        self.audit_logger.setLevel(logging.INFO)
        # Avoid adding duplicate handlers if the logger already has them.
        if not self.audit_logger.handlers:
            audit_handler = TimedRotatingFileHandler(
                f"{self.log_dir}/auditlog.log", when="midnight", interval=1
            )
            audit_handler.suffix = "%Y-%m-%d"
            audit_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            self.audit_logger.addHandler(audit_handler)

        load_dotenv()
        # Validate that required environment variables are present.
        required_vars = ["OPENAI_API_KEY", "DENO_PATH"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

        # Initialize an empty message history.
        self.history = []
        # Initialize the timestamp for the history (unix timestamp).
        self.history_timestamp = None
        # Initialize (or create) the SQLite database for tasks.
        self.init_db()

        # Run Python code sandboxed using Pyodide as a MCP server
        run_python_server = MCPServerStdio(
            os.getenv("DENO_PATH"),
            args=[
                "run",
                "-N",
                "-R=node_modules",
                "-W=node_modules",
                "--node-modules-dir=auto",
                "jsr:@pydantic/mcp-run-python",
                "stdio",
            ],
        )

        # Use Claude if Anthropic API key is set
        claude37sonnet = AnthropicModel("claude-3-7-sonnet-latest")
        claude35sonnet = AnthropicModel("claude-3-5-sonnet-latest")
        claude35haiku  = AnthropicModel("claude-3-5-haiku-latest")
        o3mini = OpenAIModel("o3-mini")
        gpt4o  = OpenAIModel("gpt-4o")
        gpt41  = OpenAIModel("gpt-4.1")
        gemini25flash = GeminiModel("gemini-2.5-flash-preview-05-20", provider="google-gla")
        gemini20flash = GeminiModel("gemini-2.0-flash", provider="google-gla")

        preferred_model = FallbackModel(
            claude35sonnet,
            claude35haiku,
        )

        # Initialize the agent with the given system prompt.
        self.agent = Agent(
            model=preferred_model,
            system_prompt=system_prompt,
            mcp_servers=[run_python_server],
        )

        # Add dynamic system prompt snippets as well.
        @self.agent.system_prompt
        def add_the_date() -> str:
            return f'The current date is {date.today()} and it is a {date.today().strftime("%A")}. The current time is {datetime.now().strftime("%H:%M")} (24-hour clock).'

        @self.agent.system_prompt
        def read_notes() -> str:
            """
            Read in the contents of the notebook file.
            """
            filepath = f"{self.notes_dir}/{self.notebook_filename}"
            if not os.path.exists(filepath):
                return ""
            with open(filepath, "r") as f:
                return (
                    "Notes you've made so far, including your thoughts and observations:\n"
                    + f.read()
                )

        @self.agent.system_prompt
        def fetch_pending_tasks() -> str:
            """
            Start every interaction with a full list of all pending tasks, to prime the answers.
            """
            tasks = query_task_database(
                "SELECT id, description, time_added, due, tags, recurrence FROM tasks WHERE time_complete IS NULL ORDER BY time_added DESC"
            )
            if not tasks:
                return ""
            return (
                "Here is a list of all pending tasks ordered by most recently added first:\n"
                + "Columns are id, description, time_added, due, tags, recurrence\n"
                + tasks
            )

        # Register agent tools as inner asynchronous functions decorated with tool_plain.
        @self.agent.tool_plain()
        def query_task_database(query: str, params: tuple = ()) -> str:
            """
            Query the task database with a given SQL query. You can read data with
            SELECT queries and update data with INSERT and UPDATE queries.
            The database is an SQLite database with a single table named 'tasks'.

            Schema for the 'tasks' table:
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                time_added TEXT NOT NULL,
                time_complete TEXT,
                due TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                recurrence TEXT DEFAULT '',
                points INT DEFAULT 1

            Important details on how to use this dataset and the fields:
            The 'time_added' and 'time_complete' fields are stored as ISO 8601 strings.
            The 'time_complete' field is empty for tasks that are not yet complete.
            When marking a task as complete, always check the 'recurrence' field to see if the task should be rescheduled.
            If a task should be rescheduled, add a new task with the same description and tags, but with a new 'due' date.
            The 'due' field can be a date, time, or a generic description of a future period.
            The 'recurrence' field is a string that describes how often the task should recur.
            The 'recurrence' field is empty for tasks that do not recur, and that applies to the majority of tasks.
            The 'tags' field is a comma-separated list of lowercased tags. Tags are used to group tasks.
            When multiple tags are used, split them by comma to understand the task better.
            The 'tags' field is empty for tasks that have no tags yet. Suggest tags that might be useful.
            The 'points' field is used as rewards for completing tasks. Small tasks award 1 point and bigger tasks more points.
            Help the user to complete tasks to increase their total XP.

            Args:
                query (str): The SQL query to execute.
                params (tuple): The parameters to pass to the query, if any.
            Returns:
                str: The result of the query as a formatted string.
            """
            try:
                rows = self.query_db(query, params)
                return "\n".join([str(row) for row in rows])
            except sqlite3.Error as e:
                return f"Error executing query: {e}"

        @self.agent.tool_plain()
        def write_notes_to_notebook(text: str) -> str:
            """
            Note down a generic observation about something you learned about the user. Only write thoughts and observations. It is not necessary to mention that the user completed a task. Task details do not belong here, only note down observations that appear to be true both today and in general. Write concisely.

            Args:
                text (str): The text to write to the notebook.
            Returns:
                str: A confirmation message.
            """
            filepath = f"{self.notes_dir}/{self.notebook_filename}"
            try:
                with open(filepath, "a") as f:
                    f.write(text + "\n")
                return "Text written to notebook."
            except Exception as e:
                return f"Error writing to notebook: {e}"

    def init_db(self):
        """
        Initialize the SQLite database and create the tasks table if it doesn't exist.
        Also, check if the 'due', 'tags', and 'recurrence' columns exist and ALTER TABLE to add them if missing.
        """
        conn = sqlite3.connect(self.DB_FILENAME)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                time_added TEXT NOT NULL,
                time_complete TEXT,
                due TEXT DEFAULT '',
                tags TEXT DEFAULT '',
                recurrence TEXT DEFAULT '',
                points INT DEFAULT 1
            )
            """
        )
        conn.commit()
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [row[1] for row in cursor.fetchall()]

        if "due" not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN due TEXT DEFAULT ''")
            conn.commit()

        if "tags" not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN tags TEXT DEFAULT ''")
            conn.commit()

        if "recurrence" not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN recurrence TEXT DEFAULT ''")
            conn.commit()

        if "points" not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN points INT DEFAULT 1")
            conn.commit()

        conn.close()

    def query_db(self, query, params=()):
        """
        Execute a query on the SQLite database and return the results.
        """
        self.log_query(query, params)
        with sqlite3.connect(self.DB_FILENAME) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.commit()
        return results

    def log_query(self, query, params):
        """
        Log the query and its parameters to the audit log.
        """
        self.audit_logger.info(f"Executed Query: {query} | Params: {params}")

    def log_messages(self, result, history):
        """
        Log each message to disk in JSON format.
        """
        # Use the entire list if this is the first interaction in the thread
        messages = result.new_messages_json() if history else result.all_messages_json()
        messages_json = to_jsonable_python(messages)

        # Use a date-stamped filename for the message history
        filepath = f"{self.log_dir}/messages.{datetime.now().strftime('%Y-%m-%d')}.json"
        with open(filepath, "a") as f:
            f.write(messages_json)

    def set_history(self, history):
        """
        Update the bot's history with the given history and record the current unix timestamp.

        Arguments:
            history: A list of messages to update the bot's history with.
        """
        self.history = history
        self.history_timestamp = time.time()

    def get_history(self):
        """
        Return the current message history. If the stored history timestamp is older than 1 hour,
        clear the history and reset the timestamp.

        Returns:
            list: The current valid history.
        """
        one_hour = 1 * 3600
        current_time = time.time()
        if self.history_timestamp and (
            current_time - self.history_timestamp > one_hour
        ):
            self.history = []
            self.history_timestamp = None
        return self.history

    async def process_message(self, text: str):
        """
        Processes a message by passing it to the agent and transforms the resulting new messages into
        a Slack Bolt block formatted dictionary. The method collects each new part from the agent's output.

        Args:
            text (str): The input text message.
        Returns:
            dict: A dictionary following the Slack Bolt block format.
        """
        self.audit_logger.info(f"Processing message: {text.strip()}")
        async with self.agent.run_mcp_servers():
            result = await self.agent.run(text, message_history=self.get_history())
        self.log_messages(result, self.history)
        self.audit_logger.info(f"Token usage: {result.usage()}")
        self.set_history(result.all_messages())

        slack_message = {"blocks": [], "text": result.data}
        for msg in result.new_messages():
            block = {
                "type": "rich_text",
                "elements": [{"type": "rich_text_section", "elements": []}],
            }
            elements = block["elements"][0]["elements"]

            for part in msg.parts:
                if isinstance(part, TextPart) and part.has_content():
                    elements.append({"type": "text", "text": part.content + "\n"})
                elif isinstance(part, ToolCallPart):
                    # Choose emoji based on tool name
                    emoji_name = "gear"

                    if part.tool_name == "query_task_database" and part.has_content():
                        # For SQL queries, customize emoji based on query type
                        query_text = str(part.args).upper().strip() if part.args else ""
                        if query_text.startswith("SELECT"):
                            emoji_name = "mag"  # Magnifying glass for SELECT
                        elif query_text.startswith("INSERT"):
                            emoji_name = "heavy_plus_sign"  # Plus for INSERT
                        elif query_text.startswith("UPDATE"):
                            emoji_name = "pencil"  # Pencil for UPDATE
                        elif query_text.startswith("DELETE"):
                            emoji_name = "wastebasket"  # Trash for DELETE
                        else:
                            emoji_name = (
                                "card_index_dividers"  # Default for other DB operations
                            )
                    elif part.tool_name == "write_notes_to_notebook":
                        emoji_name = "memo"  # Memo for notebook operations

                    elements.append({"type": "emoji", "name": emoji_name})
                    elements.append(
                        {"type": "text", "text": f" Called {part.tool_name}\n"}
                    )

            slack_message["blocks"].append(block)

        return slack_message
