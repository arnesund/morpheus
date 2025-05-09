"""
Unit tests for the query_task_database tool.
"""
import sqlite3
import pytest
from unittest.mock import MagicMock, patch

from tests.fixtures.test_data import SAMPLE_TASKS


@pytest.fixture
def populated_db(in_memory_db):
    """Populate the in-memory database with sample tasks."""
    cursor = in_memory_db.cursor()
    for task in SAMPLE_TASKS:
        cursor.execute(
            """
            INSERT INTO tasks (description, time_added, time_complete, due, tags, recurrence, points)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task["description"],
                task["time_added"],
                task["time_complete"],
                task["due"],
                task["tags"],
                task["recurrence"],
                task["points"],
            ),
        )
    in_memory_db.commit()
    return in_memory_db


@pytest.fixture
def mock_morpheus_bot(populated_db):
    """Create a mock MorpheusBot instance with a query_db method."""
    mock_bot = MagicMock()
    
    def mock_query_db(query, params=()):
        cursor = populated_db.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    
    mock_bot.query_db = mock_query_db
    mock_bot.log_query = MagicMock()
    mock_bot.DB_FILENAME = ":memory:"
    
    return mock_bot


class TestQueryTaskDatabaseTool:
    def test_query_all_tasks(self, mock_morpheus_bot):
        """Test querying all tasks."""
        from agent import MorpheusBot
        
        # Get the query_task_database function directly
        with patch.object(MorpheusBot, '__init__', return_value=None):
            bot = MorpheusBot()
            bot.query_db = mock_morpheus_bot.query_db
            bot.log_query = mock_morpheus_bot.log_query
            
            # Create the function as it would be created in the real bot
            query_task_database = lambda query, params=(): bot.query_db(query, params)
            
            # Test the function
            result = query_task_database("SELECT * FROM tasks")
            
            # We should get 3 rows (tasks)
            assert len(result.split('\n')) == 3
            assert "Task 1: Complete project review" in result
            assert "Task 2: Weekly planning session" in result
            assert "Task 3: Send follow-up emails" in result

    def test_query_pending_tasks(self, mock_morpheus_bot):
        """Test querying pending tasks."""
        from agent import MorpheusBot
        
        with patch.object(MorpheusBot, '__init__', return_value=None):
            bot = MorpheusBot()
            bot.query_db = mock_morpheus_bot.query_db
            bot.log_query = mock_morpheus_bot.log_query
            
            query_task_database = lambda query, params=(): bot.query_db(query, params)
            
            result = query_task_database(
                "SELECT * FROM tasks WHERE time_complete IS NULL"
            )
            
            # We should get 2 rows (pending tasks)
            assert len(result.split('\n')) == 2
            assert "Task 1: Complete project review" in result
            assert "Task 2: Weekly planning session" in result
            assert "Task 3: Send follow-up emails" not in result

    def test_query_with_params(self, mock_morpheus_bot):
        """Test querying with parameters."""
        from agent import MorpheusBot
        
        with patch.object(MorpheusBot, '__init__', return_value=None):
            bot = MorpheusBot()
            bot.query_db = mock_morpheus_bot.query_db
            bot.log_query = mock_morpheus_bot.log_query
            
            query_task_database = lambda query, params=(): bot.query_db(query, params)
            
            result = query_task_database(
                "SELECT * FROM tasks WHERE tags LIKE ?", 
                ("%planning%",)
            )
            
            # We should get 1 row (tasks with planning tag)
            assert len(result.split('\n')) == 1
            assert "Task 2: Weekly planning session" in result

    def test_error_handling(self, mock_morpheus_bot):
        """Test error handling for invalid queries."""
        from agent import MorpheusBot
        
        with patch.object(MorpheusBot, '__init__', return_value=None):
            bot = MorpheusBot()
            bot.query_db = MagicMock(side_effect=sqlite3.Error("Invalid SQL"))
            bot.log_query = mock_morpheus_bot.log_query
            
            query_task_database = lambda query, params=(): "\n".join([str(row) for row in bot.query_db(query, params)])
            
            # This should return an error message
            result = query_task_database("INVALID SQL")
            assert "Error executing query" in result