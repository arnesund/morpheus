"""
Global test configuration and fixtures for the Morpheus project.
"""
import os
import sqlite3
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def temp_notebook_dir(tmp_path):
    """Create a temporary directory for notebook tests."""
    notebook_dir = tmp_path / "notes"
    notebook_dir.mkdir()
    return notebook_dir

@pytest.fixture
def temp_notebook_file(temp_notebook_dir):
    """Create a temporary notebook file."""
    notebook_file = temp_notebook_dir / "test_notebook.md"
    notebook_file.write_text("# Test Notebook\n\nThis is a test notebook for testing purposes.\n")
    return notebook_file

@pytest.fixture
def in_memory_db():
    """Create an in-memory SQLite database with the tasks table."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            time_added TEXT NOT NULL,
            time_complete TEXT,
            due TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            recurrence TEXT DEFAULT '',
            points INT DEFAULT 1
        )
    """)
    conn.commit()
    yield conn
    conn.close()

@pytest.fixture
def mock_agent():
    """Create a mock Agent object."""
    mock = MagicMock()
    mock.tool_plain = MagicMock(return_value=lambda f: f)
    mock.system_prompt = MagicMock(return_value=lambda f: f)
    mock.run = AsyncMock()
    mock.run_mcp_servers = AsyncMock(return_value=AsyncMock(
        __aenter__=AsyncMock(),
        __aexit__=AsyncMock()
    ))
    return mock

@pytest.fixture
def mock_model():
    """Create a mock model (Claude, GPT, etc)."""
    return MagicMock()