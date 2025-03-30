import os
import json
import sqlite3
import logging
import time
from logging.handlers import TimedRotatingFileHandler
from datetime import date, datetime
from dotenv import load_dotenv
import openai
from pydantic_core import to_jsonable_python
from pydantic_ai import Agent

class MorpheusBot:
    def __init__(self, db_filename: str = "tasks.db", system_prompt: str = "You are Morpheus, the guide from The Matrix. You help the user manage their tasks with calm wisdom and clarity."):
        self.DB_FILENAME = db_filename

        # Ensure the required directories exist
        os.makedirs("logs", exist_ok=True)
        os.makedirs("notes", exist_ok=True)

        # Complete message history log
        self.message_history_filename = "logs/messages.json"

        # Set up the audit logger that writes to logs/auditlog.log.
        self.audit_logger = logging.getLogger("auditlog")
        self.audit_logger.setLevel(logging.INFO)
        # Avoid adding duplicate handlers if the logger already has them.
        if not self.audit_logger.handlers:
            audit_handler = TimedRotatingFileHandler("logs/auditlog.log", when="midnight", interval=1)
            audit_handler.suffix = "%Y-%m-%d"
            audit_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.audit_logger.addHandler(audit_handler)

        load_dotenv()
        # Validate that required environment variables are present.
        required_vars = ['OPENAI_API_KEY']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        # Initialize an empty message history.
        self.history = []
        # Initialize the timestamp for the history (unix timestamp).
        self.history_timestamp = None
        # Initialize (or create) the SQLite database for tasks.
        self.init_db()

        # Initialize the agent with the given system prompt.
        self.agent = Agent(
            model='openai:gpt-4o',
            system_prompt=system_prompt,
        )

        # Add dynamic system prompt snippets as well.
        @self.agent.system_prompt
        def add_the_date() -> str:
            return f'The current date is {date.today()} and it is a {date.today().strftime("%A")}.'

        @self.agent.system_prompt
        def read_notes() -> str:
            """
            Read in the contents of the notes/notebook.md file.
            """
            if not os.path.exists('notes/notebook.md'):
                return ""
            with open('notes/notebook.md', 'r') as f:
                return "Notes you've made so far, including your thoughts and observations:\n" + f.read()

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

        @self.agent.tool_plain()
        def write_notes_to_notebook(text: str) -> str:
            """
            Write the given text to your notebook. Use this tool when you want to take a note in markdown format about something you learned about the user. Do not write tasks here. Only write thoughts and observations.
            
            Args:
                text (str): The text to write to the notebook.
            Returns:
                str: A confirmation message.
            """
            try:
                with open("notes/notebook.md", "a") as f:
                    f.write(text + "\n")
                return "Text written to notebook."
            except Exception as e:
                return f"Error writing to notebook: {e}"


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

    def log_messages(self, result, history):
        """
        Log each message to disk in JSON format.
        """
        # Use the entire list if this is the first interaction in the thread
        messages = result.new_messages_json() if history else result.all_messages_json()
        messages_json = to_jsonable_python(messages)
        with open(self.message_history_filename, "a") as f:
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
        Return the current message history. If the stored history timestamp is older than 6 hours,
        clear the history and reset the timestamp.
        
        Returns:
            list: The current valid history.
        """
        six_hours = 6 * 3600
        current_time = time.time()
        if self.history_timestamp and (current_time - self.history_timestamp > six_hours):
            self.history = []
            self.history_timestamp = None
        return self.history

    async def process_message(self, text: str):
        """
        Wrapper for self.agent.run() that passes along the message history as well.
        Updates the history by calling set_history() on the returned result.
        
        Arguments:
            text: The input text to process.
        Returns:
            The result of the agent.run() call.
        """
        self.audit_logger.info(f"Processing message: {text.strip()}")
        result = await self.agent.run(text, message_history=self.get_history())
        self.log_messages(result, self.history)
        self.audit_logger.info(f"Token usage: {result.usage()}")
        self.set_history(result.all_messages())
        return result
