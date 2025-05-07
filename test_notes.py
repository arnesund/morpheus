"""Tests for the notes storage system using pytest."""

import os
import shutil
from datetime import datetime

import pytest

from agent import MorpheusBot


@pytest.fixture
def test_bot():
    """Fixture to create and clean up a test MorpheusBot instance."""
    test_dir = "test_data"
    os.makedirs(test_dir, exist_ok=True)
    test_db = f"{test_dir}/test_morpheus.db"

    if os.path.exists(test_db):
        os.remove(test_db)

    bot = MorpheusBot(db_filename=test_db, log_dir=test_dir, notes_dir=test_dir)

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
    result = test_bot.write_notes_to_notebook(
        "This note has a custom timestamp.", "Observation", custom_timestamp
    )
    assert "Note added to category: Observation" in result


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
