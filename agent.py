import asyncio
import json
import logging
import os
import random
import sqlite3
import sys
import time
from datetime import date, datetime, timedelta
from logging.handlers import TimedRotatingFileHandler

import openai
from dotenv import load_dotenv
from pydantic_ai import Agent, capture_run_messages
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai.messages import TextPart, ToolCallPart
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_core import to_jsonable_python


class MorpheusBot:
    def __init__(
        self,
        db_filename: str = "tasks.db",
        system_prompt: str = "You are Morpheus, the guide from The Matrix. You help the user manage their tasks with calm wisdom and clarity.",
        notebook_filename: str = "notebook.md",
        testing_mode: bool = False,
    ):
        self.DB_FILENAME = db_filename
        self.log_dir = "logs"
        self.notes_dir = "notes"
        self.notebook_filename = notebook_filename
        self.testing_mode = testing_mode

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

        if not testing_mode:
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

        if not testing_mode:
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
            claude35haiku = AnthropicModel("claude-3-5-haiku-latest")
            o3mini = OpenAIModel("o3-mini")
            gpt4o = OpenAIModel("gpt-4o")
            gpt41 = OpenAIModel("gpt-4.1")

            preferred_model = FallbackModel(
                claude37sonnet, claude35haiku, o3mini, gpt4o
            )

            # Initialize the agent with the given system prompt.
            self.agent = Agent(
                model=preferred_model,
                system_prompt=system_prompt,
                mcp_servers=[run_python_server],
            )

        if testing_mode:
            self.write_notes_to_notebook = self._write_notes_to_notebook
            self.read_notes_from_notebook = self._read_notes_from_notebook

    def _write_notes_to_notebook(
        self, text: str, category: str = "Observation", timestamp: str = None
    ) -> str:
        """
        Write a note to the database with the given text, category, and timestamp.
        This is a direct implementation for testing mode.
        """
        if not text.strip():
            return "Note content cannot be empty."

        if not timestamp:
            timestamp = datetime.now().isoformat()

        try:
            self.query_db(
                "INSERT INTO notes (content, category, timestamp) VALUES (?, ?, ?)",
                (text, category, timestamp),
            )
            return f"Note added to category: {category}"
        except sqlite3.Error as e:
            return f"Error adding note: {e}"

    def _read_notes_from_notebook(
        self, category: str = None, content_contains: str = None, days_ago: int = None
    ) -> str:
        """
        Read notes from the database with optional filtering.
        This is a direct implementation for testing mode.
        """
        try:
            query = "SELECT content, category, timestamp FROM notes"
            params = []
            where_clauses = []

            if category:
                where_clauses.append("category = ?")
                params.append(category)

            if content_contains:
                where_clauses.append("content LIKE ?")
                params.append(f"%{content_contains}%")

            if days_ago:
                date_n_days_ago = (
                    datetime.now() - timedelta(days=days_ago)
                ).isoformat()
                where_clauses.append("timestamp >= ?")
                params.append(date_n_days_ago)

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)

            query += " ORDER BY timestamp DESC"

            rows = self.query_db(query, tuple(params))

            if not rows:
                return "No notes found matching the filter criteria."

            result = "Notes"
            if category:
                result += f" in category '{category}'"
            if content_contains:
                result += f" containing '{content_contains}'"
            if days_ago:
                result += f" from the last {days_ago} days"
            result += ":\n\n"

            categories = {}
            for row in rows:
                content, category, timestamp = row
                if category not in categories:
                    categories[category] = []
                date_str = datetime.fromisoformat(timestamp).strftime("%Y-%m-%d")
                categories[category].append((content, date_str))

            for category, content_items in categories.items():
                result += f"### {category}\n"
                for content, date in content_items:
                    result += f"- [{date}] {content}\n"
                result += "\n"

            return result
        except sqlite3.Error as e:
            return f"Error reading notes: {e}"
        except Exception as e:
            return f"Error: {e}"

    def init_db(self):
        """
        Initialize the SQLite database and create the tasks and notes tables if they don't exist.
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

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT NOT NULL,
                timestamp TEXT NOT NULL
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
