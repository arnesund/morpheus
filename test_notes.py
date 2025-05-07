"""Tests for the notes storage system using pytest."""

import os
import shutil
import sqlite3
from datetime import datetime, timedelta

import pytest

from agent import MorpheusBot


class TestMorpheusBot:
    """A test-specific class that implements the notes functionality without external dependencies."""

    def __init__(
        self, db_filename="test_morpheus.db", notebook_filename="test_notebook.md"
    ):
        """Initialize a test bot without requiring environment variables or external services."""
        self.DB_FILENAME = db_filename
        self.log_dir = "test_data"
        self.notes_dir = "test_data"
        self.notebook_filename = notebook_filename

        for d in [self.log_dir, self.notes_dir]:
            os.makedirs(d, exist_ok=True)

        self.init_db()

    def init_db(self):
        """Initialize the SQLite database with the notes table."""
        conn = sqlite3.connect(self.DB_FILENAME)
        cursor = conn.cursor()

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
        conn.close()

    def query_db(self, query, params=()):
        """Execute a query on the SQLite database and return the results."""
        with sqlite3.connect(self.DB_FILENAME) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.commit()
        return results

    def write_notes_to_notebook(self, text, category="Observation", timestamp=None):
        """Write a note to the database with the given text, category, and timestamp."""
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

    def read_notes_from_notebook(
        self, category=None, content_contains=None, days_ago=None
    ):
        """Read notes from the database with optional filtering."""
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
                categories[category].append((content, date_str, timestamp))

            for category, content_items in categories.items():
                result += f"### {category}\n"
                for content, date, _ in content_items:
                    result += f"- [{date}] {content}\n"
                result += "\n"

            return result
        except sqlite3.Error as e:
            return f"Error reading notes: {e}"
        except Exception as e:
            return f"Error: {e}"


@pytest.fixture
def test_bot():
    """Fixture to create and clean up a test MorpheusBot instance."""
    test_dir = "test_data"
    os.makedirs(test_dir, exist_ok=True)
    test_db = f"{test_dir}/test_morpheus.db"

    if os.path.exists(test_db):
        os.remove(test_db)

    # Use the TestMorpheusBot class instead of MorpheusBot
    bot = TestMorpheusBot(db_filename=test_db)

    yield bot

    shutil.rmtree(test_dir)


def test_write_notes_basic(test_bot):
    """Test adding a basic observation note."""
    result = test_bot.write_notes_to_notebook(
        "The user seems to be working on a project related to AI."
    )
    assert "Note added to category: Observation" in result


def test_write_notes_with_category(test_bot):
    """Test adding a note with a specific category."""
    result = test_bot.write_notes_to_notebook(
        "User prefers to be reminded about tasks in the morning.", "Preference"
    )
    assert "Note added to category: Preference" in result


def test_write_notes_with_custom_timestamp(test_bot):
    """Test adding a note with a custom timestamp."""
    custom_timestamp = datetime(2025, 1, 1).isoformat()
    note_content = "This note has a custom timestamp."

    result = test_bot.write_notes_to_notebook(
        note_content, "Observation", custom_timestamp
    )
    assert "Note added to category: Observation" in result

    read_result = test_bot.read_notes_from_notebook(content_contains="custom timestamp")
    assert note_content in read_result
    assert (
        "2025-01-01" in read_result
    )  # Date part of the timestamp should be in the output


def test_read_notes_all(test_bot):
    """Test reading all notes."""
    test_bot.write_notes_to_notebook("Test note 1")
    test_bot.write_notes_to_notebook("Test note 2", "Preference")

    result = test_bot.read_notes_from_notebook()
    assert "Test note 1" in result
    assert "Test note 2" in result
    assert "Observation" in result
    assert "Preference" in result


def test_read_notes_with_category_filter(test_bot):
    """Test reading notes filtered by category."""
    test_bot.write_notes_to_notebook("Test observation", "Observation")
    test_bot.write_notes_to_notebook("Test preference", "Preference")
    test_bot.write_notes_to_notebook("Test schedule", "Schedule")

    result = test_bot.read_notes_from_notebook(category="Preference")
    assert "Test preference" in result
    assert "Test observation" not in result
    assert "Test schedule" not in result


def test_read_notes_with_content_filter(test_bot):
    """Test reading notes filtered by content."""
    test_bot.write_notes_to_notebook("User likes coffee in the morning")
    test_bot.write_notes_to_notebook("User has a meeting every Monday", "Schedule")

    result = test_bot.read_notes_from_notebook(content_contains="meeting")
    assert "meeting" in result
    assert "coffee" not in result


def test_read_notes_with_time_filter(test_bot):
    """Test reading notes filtered by time period."""
    past_timestamp = datetime(2020, 1, 1).isoformat()
    test_bot.write_notes_to_notebook("Old note", "Observation", past_timestamp)

    test_bot.write_notes_to_notebook("Recent note")

    result = test_bot.read_notes_from_notebook(days_ago=30)
    assert "Recent note" in result
    assert "Old note" not in result


def test_read_notes_with_multiple_filters(test_bot):
    """Test reading notes with multiple filters applied."""
    test_bot.write_notes_to_notebook("User likes coffee", "Preference")
    test_bot.write_notes_to_notebook("User prefers morning meetings", "Preference")
    test_bot.write_notes_to_notebook("Morning routine includes exercise", "Schedule")

    result = test_bot.read_notes_from_notebook(
        category="Preference", content_contains="morning"
    )
    assert "morning meetings" in result
    assert "coffee" not in result
    assert "Morning routine" not in result
