import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import openai
from pydantic_ai import Agent

# Load environment variables and set OpenAI API key
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Define the SQLite database file name
DB_FILENAME = "tasks.db"

# Initialize the Pydantic AI agent (using GPT-4o)
agent = Agent('openai:gpt-4o')

# Create the tasks table if it doesn't already exist
def init_db():
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            time_added TEXT NOT NULL,
            time_complete TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@agent.tool_plain()
def list_tasks() -> str:
    """
    List all tasks stored in the database.
    Returns a formatted string of all tasks with their ID, description, time added, and time complete status.
    """
    conn = sqlite3.connect(DB_FILENAME)
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
        output_lines.append(f"ID: {task_id}, Description: {description}, Added: {time_added}, Completed: {completed_str} (Status: {status})")
    return "\n".join(output_lines)

@agent.tool_plain()
def add_task(description: str) -> str:
    """
    Add a new task with the given description.
    
    Argument:
      - description: The text description of the task.
    
    Returns a confirmation message with the new task's ID.
    """
    current_time = datetime.now().isoformat()
    conn = sqlite3.connect(DB_FILENAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tasks (description, time_added) VALUES (?, ?)", (description, current_time))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return f"Task added with ID: {new_id}"

@agent.tool_plain()
def update_task(task_id: int, description: str = None, complete: bool = False) -> str:
    """
    Update an existing task.
    
    Arguments:
      - task_id: The ID of the task to update.
      - description: (Optional) New description text for the task.
      - complete: (Optional) If true, marks the task as complete and sets time_complete to the current time.
    
    Returns a success message or an error message if the task doesn’t exist.
    """
    conn = sqlite3.connect(DB_FILENAME)
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
        return "No updates provided."
    
    params.append(task_id)
    query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    return f"Task with ID {task_id} updated successfully."
