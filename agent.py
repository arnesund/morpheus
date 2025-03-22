import os
import sqlite3
import logging
from datetime import datetime
from dotenv import load_dotenv
import openai
from pydantic_ai import Agent

class MorpheusBot:
    def __init__(self, db_filename: str = "tasks.db", system_prompt: str = "You are Morpheus, the guide from The Matrix. You help the user manage their tasks with calm wisdom and clarity."):
        self.DB_FILENAME = db_filename

        # Ensure the logs directory exists for audit logs.
        os.makedirs("logs", exist_ok=True)

        # Set up the audit logger that writes to logs/auditlog.log.
        self.audit_logger = logging.getLogger("auditlog")
        self.audit_logger.setLevel(logging.INFO)
        # Avoid adding duplicate handlers if the logger already has them.
        if not self.audit_logger.handlers:
            audit_handler = logging.FileHandler("logs/auditlog.log")
            audit_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.audit_logger.addHandler(audit_handler)

        load_dotenv()
        # Validate that required environment variables are present.
        required_vars = ['OPENAI_API_KEY']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        self.agent = Agent(
            model = 'openai:gpt-4o',
            system_prompt = system_prompt,
        )

        # Initialize an empty message history.
        self.history = []
        # Initialize (or create) the SQLite database for tasks.
        self.init_db()

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
                time_complete TEXT
                due TEXT DEFAULT ''
                tags TEXT DEFAULT ''

            Important notes:
            The 'time_added' and 'time_complete' fields are stored as ISO 8601 strings.
            The 'time_complete' field is empty for tasks that are not yet complete.
            The 'due' field can be a date, time, or a generic description of a future period.
            The 'tags' field is a comma-separated list of lowercased tags. Tags are used to group tasks.
            When multiple tags are used, split them by comma to understand the task better.
            The 'tags' field is empty for tasks that have no tags yet. Suggest tags that might be useful.

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

    def init_db(self):
        """
        Initialize the SQLite database and create the tasks table if it doesn't exist.
        Also, check if the 'due' and 'tags' columns exist and ALTER TABLE to add them if missing.
        """
        conn = sqlite3.connect(self.DB_FILENAME)
        cursor = conn.cursor()
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT NOT NULL,
                time_added TEXT NOT NULL,
                time_complete TEXT
            )
            '''
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

    def update_history(self, history):
        """
        Update the bot's history with the given history, filtered to keep only
        the relevant entries.

        Arguments:
            history: A list of messages to update the bot's history with.
        """
        self.history = history

    async def process_message(self, text: str):
        """
        Wrapper for self.agent.run() that passes along the message history as well.
        Updates self.history by calling all_messages() on the returned result.

        Arguments:
            text: The input text to process.
        Returns:
            The result of the agent.run() call.
        """
        self.audit_logger.info(f"Processing message: {text.strip()}")
        result = await self.agent.run(text, message_history=self.history)
        self.audit_logger.info(f"Token usage: {result.usage()}")
        self.update_history(result.all_messages())
        return result
