import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import openai
from pydantic_ai import Agent

class MorpheusBot:
    DB_FILENAME = "tasks.db"  # Name of the SQLite database file

    def __init__(self):
        # Load environment variables from .env
        load_dotenv()
        # Validate that required environment variables are present. Adjust as needed.
        required_vars = ['OPENAI_API_KEY']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        # Set the OpenAI API key.
        openai.api_key = os.getenv("OPENAI_API_KEY")
        # Initialize the agent. (This example uses GPT-4o; adjust as needed.)
        self.agent = Agent('openai:gpt-4o')
        # Initialize an empty message history.
        self.history = []
        # Initialize (or create) the SQLite database for tasks.
        self.init_db()

        # Register agent tools as inner functions decorated with tool_plain.
        @self.agent.tool_plain()
        def list_tasks() -> str:
            """
            List all tasks stored in the database.
            Returns a formatted string of tasks with their ID, description, time added,
            due date/time/statement, tags, and completion status.
            """
            conn = sqlite3.connect(MorpheusBot.DB_FILENAME)
            cursor = conn.cursor()
            cursor.execute("SELECT id, description, time_added, time_complete, due, tags FROM tasks")
            rows = cursor.fetchall()
            conn.close()
            if not rows:
                return "No tasks found."
            output_lines = []
            for row in rows:
                task_id, description, time_added, time_complete, due, tags = row
                status = "Completed" if time_complete is not None else "Pending"
                completed_str = time_complete if time_complete is not None else "N/A"
                due_str = due if due else "N/A"
                tags_clean = tags.strip() if tags else ""
                tags_str = tags_clean if tags_clean else "N/A"
                output_lines.append(
                    f"ID: {task_id}, Description: {description}, Added: {time_added}, "
                    f"Due: {due_str}, Tags: {tags_str}, Completed: {completed_str} (Status: {status})"
                )
            return "\n".join(output_lines)

        @self.agent.tool_plain()
        def add_task(description: str, due: str = "", tags: str = "") -> str:
            """
            Add a new task with the given description, with optional due information and tags.
            Arguments:
            - description: Text description for the task.
            - due: (Optional) A string representing due date/time or a generic due statement.
            - tags: (Optional) Comma-separated list of tags.
            Returns a confirmation message with the new task's ID.
            """
            current_time = datetime.now().isoformat()
            conn = sqlite3.connect(MorpheusBot.DB_FILENAME)
            cursor = conn.cursor()
            # Ensure that tags and due default to empty strings if not provided.
            tags = tags.strip()
            due = due.strip()
            cursor.execute(
                "INSERT INTO tasks (description, time_added, due, tags) VALUES (?, ?, ?, ?)",
                (description, current_time, due, tags)
            )
            conn.commit()
            new_id = cursor.lastrowid
            conn.close()
            return f"Task added with ID: {new_id}"

        @self.agent.tool_plain()
        def update_task(task_id: int, description: str = None, complete: bool = False) -> str:
            """
            Update an existing task.
            Arguments:
            - task_id: The ID of the task to update.
            - description: (Optional) New description text.
            - complete: (Optional) If True, mark the task as complete (sets time_complete to now).
            Returns a success message or an error message if task not found.
            """
            conn = sqlite3.connect(MorpheusBot.DB_FILENAME)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
            if cursor.fetchone() is None:
                conn.close()
                return f"Task with ID {task_id} does not exist."
            updates = []
            params = []
            if description is not None:
                updates.append("description = ?")
                params.append(description)
            if complete:
                updates.append("time_complete = ?")
                params.append(datetime.now().isoformat())
            if not updates:
                conn.close()
                return "No updates were provided."
            params.append(task_id)
            query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            conn.close()
            return f"Task with ID {task_id} updated successfully."

        @self.agent.tool_plain()
        def add_tags(task_id: int, tags: list[str]) -> str:
            """
            Add tags to an existing task identified by task_id.
            This function will merge new tags with any existing ones (ensuring they remain unique).
            Arguments:
            - task_id: The ID of the task to update.
            - tags: List of tags (strings) to add.
            Returns a confirmation message or an error message if task not found.
            """
            conn = sqlite3.connect(MorpheusBot.DB_FILENAME)
            cursor = conn.cursor()
            cursor.execute("SELECT tags FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if row is None:
                conn.close()
                return f"Task with ID {task_id} does not exist."
            current_tags_str = row[0].strip() if row[0] else ""
            current_tags = set(tag.strip() for tag in current_tags_str.split(",") if tag.strip())
            new_tags = set(tag.strip() for tag in tags if tag.strip())
            updated_tags = current_tags.union(new_tags)
            updated_tags_str = ", ".join(sorted(updated_tags))
            cursor.execute("UPDATE tasks SET tags = ? WHERE id = ?", (updated_tags_str, task_id))
            conn.commit()
            conn.close()
            return f"Tags updated for task with ID {task_id}: {updated_tags_str if updated_tags_str else 'None'}"

        @self.agent.tool_plain()
        def update_due(task_id: int, due: str) -> str:
            """
            Update the due information for an existing task identified by task_id.
            The due parameter can be a specific date/time or a more generic statement like 'this summer'.
            Arguments:
            - task_id: The ID of the task to update.
            - due: A string representing due date/time or a due statement.
            Returns a success message or an error message if the task is not found.
            """
            conn = sqlite3.connect(MorpheusBot.DB_FILENAME)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
            if cursor.fetchone() is None:
                conn.close()
                return f"Task with ID {task_id} does not exist."
            cursor.execute("UPDATE tasks SET due = ? WHERE id = ?", (due, task_id))
            conn.commit()
            conn.close()
            return f"Due date/statement updated for task with ID {task_id}."

        # Assign these tool functions to instance variables.
        self.list_tasks = list_tasks
        self.add_task = add_task
        self.update_task = update_task
        self.add_tags = add_tags
        self.update_due = update_due

    def init_db(self):
        """
        Initialize the SQLite database and create the tasks table if it doesn't exist.
        Also, check if the 'due' and 'tags' columns exist and ALTER TABLE to add them if missing.
        """
        conn = sqlite3.connect(MorpheusBot.DB_FILENAME)
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

    async def process_message(self, text: str):
        """
        Wrapper for self.agent.run() that passes along the message history as well.
        Updates self.history by calling all_messages() on the returned result.
        Arguments:
            text: The input text to process.
        Returns:
            The result of the agent.run() call.
        """
        result = await self.agent.run(text, message_history=self.history)
        self.history = result.all_messages()
        return result
