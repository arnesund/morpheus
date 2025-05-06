"""Test script for the new notes storage system."""

import os
import shutil

from notes_utils import Note, add_note, load_notes

TEST_DIR = "test_notes"
os.makedirs(TEST_DIR, exist_ok=True)
TEST_NOTEBOOK = f"{TEST_DIR}/test_notebook.md"

if os.path.exists(TEST_NOTEBOOK):
    os.remove(TEST_NOTEBOOK)

print("Testing note addition...")

success, message = add_note(
    TEST_NOTEBOOK, "The user seems to be working on a project related to AI."
)
print(f"Test 1: {message}")

success, message = add_note(
    TEST_NOTEBOOK,
    "[PREFERENCE] User prefers to be reminded about tasks in the morning.",
)
print(f"Test 2: {message}")

success, message = add_note(
    TEST_NOTEBOOK, "User completed the database migration task yesterday."
)
print(f"Test 3: {message}")

success, message = add_note(
    TEST_NOTEBOOK, "The user is working on an AI-related project."
)
print(f"Test 4: {message}")

success, message = add_note(
    TEST_NOTEBOOK, "[SCHEDULE] User has a weekly meeting every Monday at 10am."
)
print(f"Test 5: {message}")

success, message = add_note(
    TEST_NOTEBOOK, "[SCHEDULE] User has a weekly meeting every Monday at 10am."
)
print(f"Test 6: {message}")

notes = load_notes(TEST_NOTEBOOK)
print("\nNotes in file:")
for note in notes:
    print(f"Category: {note.category}")
    print(f"Content: {note.content}")
    print(f"Timestamp: {note.timestamp}")
    print("-" * 40)

print("\nCleaning up...")
shutil.rmtree(TEST_DIR)
print("Done!")
