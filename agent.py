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

        for d in [self.log_dir, self.notes_dir]:
            os.makedirs(d, exist_ok=True)

        self.audit_logger = logging.getLogger("auditlog")
        self.audit_logger.setLevel(logging.INFO)
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
            required_vars = ["OPENAI_API_KEY", "DENO_PATH"]
            missing_vars = [var for var in required_vars if not os.getenv(var)]
            if missing_vars:
                raise ValueError(
                    f"Missing required environment variables: {', '.join(missing_vars)}"
                )

        self.history = []
        self.history_timestamp = None
        self.init_db()

        if not testing_mode:
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

            claude37sonnet = AnthropicModel("claude-3-7-sonnet-latest")
            claude35sonnet = AnthropicModel("claude-3-5-sonnet-latest")
            claude35haiku = AnthropicModel("claude-3-5-haiku-latest")
            o3mini = OpenAIModel("o3-mini")
            gpt4o = OpenAIModel("gpt-4o")
            gpt41 = OpenAIModel("gpt-4.1")

            preferred_model = FallbackModel(
                claude37sonnet, claude35haiku, o3mini, gpt4o
            )

            self.agent = Agent(
                model=preferred_model,
                system_prompt=system_prompt,
                mcp_servers=[run_python_server],
            )

            @self.agent.system_prompt
            def add_the_date() -> str:
                return f'The current date is {date.today()} and it is a {date.today().strftime("%A")}.'

            @self.agent.system_prompt
            def read_notes() -> str:
                """
                Read notes from the database and format them by category.
                """
                try:
                    rows = self.query_db(
                        "SELECT content, category, timestamp FROM notes ORDER BY timestamp DESC"
                    )

                    if not rows:
                        return ""

                    result = "Notes you've made so far, organized by category:\n\n"

                    categories = {}
                    for row in rows:
                        content, category, timestamp = row
                        if category not in categories:
                            categories[category] = []
                        categories[category].append(content)

                    for category, contents in categories.items():
                        result += f"### {category}\n"
                        for content in contents:
                            result += f"- {content}\n"
                        result += "\n"

                    return result
                except sqlite3.Error as e:
                    return f"Error reading notes: {e}"

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
            def read_notes_from_notebook(
                category: str = None, content_contains: str = None, days_ago: int = None
            ) -> str:
                """
                Read notes from the database with optional filtering by category, content substring, and time period.

                Args:
                    category (str, optional): Filter notes by category (e.g., "Preference", "Schedule", "Observation").
                    content_contains (str, optional): Filter notes by substring in content.
                    days_ago (int, optional): Filter notes from the last N days.
                Returns:
                    str: Formatted notes matching the filter criteria.
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
                        date_str = datetime.fromisoformat(timestamp).strftime(
                            "%Y-%m-%d"
                        )
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

            @self.agent.tool_plain()
            def write_notes_to_notebook(
                text: str, category: str = "Observation", timestamp: str = None
            ) -> str:
                """
                Write a note to the database with the given text, category, and timestamp.
                Use this tool to record important memories about the user that are NOT task-related.

                Suggested categories include (but are not limited to):
                - Preference: for user preferences, likes, dislikes, etc.
                - Schedule: for recurring events, meetings, routines, etc.
                - Observation: for general observations about the user

                You can use any category name that makes sense for organizing the note.

                Do NOT use this for task-related information such as task completion status, due dates, or deadlines.
                Task information belongs in the task database, not in notes.

                Args:
                    text (str): The content of the note to write.
                    category (str): The category of the note (Preference, Schedule, Observation).
                    timestamp (str, optional): Timestamp for when the note was created. Defaults to current time.
                Returns:
                    str: A confirmation message.
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
        messages = result.new_messages_json() if history else result.all_messages_json()
        messages_json = to_jsonable_python(messages)

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

        Arguments:
            text: The message text to process.

        Returns:
            A tuple of (blocks, history) where blocks is a list of Slack Bolt blocks and history is the updated history.
        """
        history = self.get_history()
        result = await capture_run_messages(
            self.agent.run_async(text=text, history=history)
        )
        self.log_messages(result, history)
        self.set_history(result.all_messages())

        blocks = []
        for message in result.new_messages():
            for part in message.parts:
                if isinstance(part, TextPart):
                    blocks.append(
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": part.text},
                        }
                    )
                elif isinstance(part, ToolCallPart):
                    blocks.append(
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*Tool Call:* `{part.name}`\n```\n{part.input}\n```\n*Result:*\n```\n{part.output}\n```",
                            },
                        }
                    )

        return blocks, result.all_messages()
