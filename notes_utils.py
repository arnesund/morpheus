"""Utilities for managing and organizing notes in the Morpheus agent."""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class Note:
    """Class representing a structured note with category and content."""

    def __init__(self, category: str, content: str, timestamp: Optional[str] = None):
        """
        Initialize a new note.

        Args:
            category: The category of the note (observation, preference, etc.)
            content: The content of the note
            timestamp: Optional timestamp for when the note was created
        """
        self.category = category
        self.content = content
        self.timestamp = timestamp or datetime.now().isoformat()

    def to_dict(self) -> Dict:
        """Convert the note to a dictionary."""
        return {
            "category": self.category,
            "content": self.content,
            "timestamp": self.timestamp,
        }

    def to_markdown(self) -> str:
        """Convert the note to a markdown string."""
        return f"## {self.category}\n{self.content}\n\n*Added: {self.timestamp}*\n\n---\n\n"

    @classmethod
    def from_dict(cls, data: Dict) -> "Note":
        """Create a Note object from a dictionary."""
        return cls(
            category=data.get("category", "Observation"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp"),
        )


def extract_category_from_text(text: str) -> Tuple[str, str]:
    """
    Extract a category from the text if present, otherwise assign a default category.

    Returns:
        A tuple of (category, content)
    """
    category_match = re.match(r"^\[([A-Za-z ]+)\](.+)", text.strip(), re.DOTALL)

    if category_match:
        category = category_match.group(1).strip().title()
        content = category_match.group(2).strip()
    else:
        if re.search(r"prefer|like|dislike|want|need", text, re.IGNORECASE):
            category = "Preference"
        elif re.search(r"schedule|every|daily|weekly|monthly", text, re.IGNORECASE):
            category = "Schedule"
        else:
            category = "Observation"
        content = text.strip()

    return category, content


def is_task_related(text: str) -> bool:
    """
    Determine if the text is related to tasks and should not be stored as a note.

    Returns:
        True if the text is task-related, False otherwise
    """
    task_keywords = [
        r"complete[d]? task",
        r"finish[ed]? task",
        r"task.*done",
        r"added.*task",
        r"created.*task",
        r"marked.*complete",
        r"due date",
        r"deadline",
        r"todo",
        r"to-do",
        r"to do",
    ]

    for keyword in task_keywords:
        if re.search(keyword, text, re.IGNORECASE):
            return True

    return False


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two text strings using a simple Jaccard similarity.

    Returns:
        A float between 0 and 1 representing similarity (1 being identical)
    """
    tokens1 = set(re.findall(r"\b\w+\b", text1.lower()))
    tokens2 = set(re.findall(r"\b\w+\b", text2.lower()))

    intersection = len(tokens1.intersection(tokens2))
    union = len(tokens1.union(tokens2))

    if union == 0:
        return 0

    return intersection / union


def load_notes(filepath: str) -> List[Note]:
    """
    Load notes from a markdown file.

    Args:
        filepath: Path to the markdown file

    Returns:
        A list of Note objects
    """
    notes = []

    if not os.path.exists(filepath):
        return notes

    try:
        with open(filepath, "r") as f:
            content = f.read()

        if "<!-- NOTES_JSON:" in content and " -->" in content:
            json_match = re.search(r"<!-- NOTES_JSON: (.*?) -->", content, re.DOTALL)
            if json_match:
                notes_data = json.loads(json_match.group(1))
                notes = [Note.from_dict(note_data) for note_data in notes_data]
        else:
            sections = re.split(r"\n\s*---\s*\n", content)
            for section in sections:
                if not section.strip():
                    continue

                category_match = re.match(
                    r"##\s+([A-Za-z ]+)\n(.+?)(\n\n\*Added:.+)?$",
                    section.strip(),
                    re.DOTALL,
                )
                if category_match:
                    category = category_match.group(1).strip()
                    content = category_match.group(2).strip()
                    timestamp_match = re.search(r"\*Added:\s+(.+?)\*", section)
                    timestamp = (
                        timestamp_match.group(1)
                        if timestamp_match
                        else datetime.now().isoformat()
                    )
                    notes.append(Note(category, content, timestamp))
                else:
                    category, content = extract_category_from_text(section)
                    notes.append(Note(category, content))
    except Exception as e:
        print(f"Error loading notes: {e}")

    return notes


def save_notes(notes: List[Note], filepath: str) -> bool:
    """
    Save notes to a markdown file with JSON metadata.

    Args:
        notes: List of Note objects
        filepath: Path to save the markdown file

    Returns:
        True if successful, False otherwise
    """
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        markdown_content = "# Notes\n\n"
        notes_json = [note.to_dict() for note in notes]

        markdown_content += f"<!-- NOTES_JSON: {json.dumps(notes_json)} -->\n\n"

        for note in notes:
            markdown_content += note.to_markdown()

        with open(filepath, "w") as f:
            f.write(markdown_content)

        return True
    except Exception as e:
        print(f"Error saving notes: {e}")
        return False


def add_note(filepath: str, text: str) -> Tuple[bool, str]:
    """
    Add a new note to the notebook, handling categorization, deduplication, and similarity.

    Args:
        filepath: Path to the notebook file
        text: Text to add as a note

    Returns:
        Tuple of (success, message)
    """
    if is_task_related(text):
        return (
            False,
            "Note appears to be task-related and should be stored in the task database instead.",
        )

    category, content = extract_category_from_text(text)
    new_note = Note(category, content)

    notes = load_notes(filepath)

    for i, note in enumerate(notes):
        similarity = calculate_similarity(note.content, new_note.content)

        if similarity > 0.8:
            return (
                False,
                "Note is nearly identical to an existing note and was not added.",
            )

        if similarity > 0.5 and note.category == new_note.category:
            combined_content = f"{note.content}\n\nAdditionally: {new_note.content}"
            notes[i] = Note(note.category, combined_content, note.timestamp)
            save_notes(notes, filepath)
            return True, "Note was merged with a similar existing note."

    notes.append(new_note)
    save_notes(notes, filepath)
    return True, f"Note added to category: {category}"
