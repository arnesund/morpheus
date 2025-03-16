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
            Returns a formatted string of tasks with their ID, description, time added, and completion status.
            """
            conn = sqlite3.connect(MorpheusBot.DB_FILENAME)
            cursor = conn.cursor()
            cursor.execute("SELECT id, description, time_added, time_complete FROM tasks")
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return "No tasks found."
            
            output_lines = []
            for row in rows:
                task_id, description, time_added, time_complete = row
                status = "Completed" if time_complete is not None else "Pending"
                completed_str = time_complete if time_complete is not None else "N/A"
                output_lines.append(
                    f"ID: {task_id}, Description: {description}, Added: {time_added}, "
                    f"Completed: {completed_str} (Status: {status})"
                )
            return "\n".join(output_lines)

        @self.agent.tool_plain()
        def add_task(description: str) -> str:
            """
            Add a new task with the given description.
            
            Arguments:
            - description: Text description for the task.
            
            Returns a confirmation message with the new task's ID.
            """
            current_time = datetime.now().isoformat()
            conn = sqlite3.connect(MorpheusBot.DB_FILENAME)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tasks (description, time_added) VALUES (?, ?)",
                           (description, current_time))
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
            
            # Check if the task exists.
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

        # Optionally, assign these tool functions to instance variables.
        self.list_tasks = list_tasks
        self.add_task = add_task
        self.update_task = update_task

    def init_db(self):
        """Initialize the SQLite database and create the tasks table if it doesn't exist."""
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
        # Run the agent including the message history.
        result = await self.agent.run(text, message_history=self.history)
        # Update history using result.all_messages() (assuming this method exists).
        self.history = result.all_messages()
        return result
