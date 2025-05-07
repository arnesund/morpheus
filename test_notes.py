"""Test script for the new notes storage system using SQLite."""

import os
import sqlite3
from datetime import datetime

TEST_DB = "test_notes.db"

if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

conn = sqlite3.connect(TEST_DB)
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

print("Testing note addition...")


def add_note(content, category="Observation", timestamp=None):
    if not timestamp:
        timestamp = datetime.now().isoformat()

    try:
        cursor.execute(
            "INSERT INTO notes (content, category, timestamp) VALUES (?, ?, ?)",
            (content, category, timestamp),
        )
        conn.commit()
        return True, f"Note added to category: {category}"
    except sqlite3.Error as e:
        return False, f"Error adding note: {e}"


success, message = add_note("The user seems to be working on a project related to AI.")
print(f"Test 1: {message}")

success, message = add_note(
    "User prefers to be reminded about tasks in the morning.", "Preference"
)
print(f"Test 2: {message}")

success, message = add_note("User completed the database migration task yesterday.")
print(f"Test 3: {message}")

success, message = add_note("The user is working on an AI-related project.")
print(f"Test 4: {message}")

success, message = add_note(
    "User has a weekly meeting every Monday at 10am.", "Schedule"
)
print(f"Test 5: {message}")

custom_timestamp = datetime(2025, 1, 1).isoformat()
success, message = add_note(
    "This note has a custom timestamp.", "Observation", custom_timestamp
)
print(f"Test 6: {message}")

print("\nNotes in database:")
cursor.execute("SELECT content, category, timestamp FROM notes ORDER BY timestamp DESC")
notes = cursor.fetchall()

for note in notes:
    content, category, timestamp = note
    print(f"Category: {category}")
    print(f"Content: {content}")
    print(f"Timestamp: {timestamp}")
    print("-" * 40)

print("\nNotes by category:")
categories = {}
for note in notes:
    content, category, timestamp = note
    if category not in categories:
        categories[category] = []
    categories[category].append(content)

for category, contents in categories.items():
    print(f"### {category}")
    for content in contents:
        print(f"- {content}")
    print()

conn.close()
os.remove(TEST_DB)
print("Done!")
