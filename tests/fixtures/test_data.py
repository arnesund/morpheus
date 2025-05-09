"""
Test data fixtures for Morpheus tests.
"""
from datetime import datetime, timedelta

# Sample task data for database tests
SAMPLE_TASKS = [
    {
        "description": "Task 1: Complete project review",
        "time_added": (datetime.now() - timedelta(days=2)).isoformat(),
        "time_complete": None,
        "due": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
        "tags": "work,project,review",
        "recurrence": "",
        "points": 2
    },
    {
        "description": "Task 2: Weekly planning session",
        "time_added": (datetime.now() - timedelta(days=1)).isoformat(),
        "time_complete": None,
        "due": datetime.now().strftime("%Y-%m-%d"),
        "tags": "planning,weekly",
        "recurrence": "weekly",
        "points": 1
    },
    {
        "description": "Task 3: Send follow-up emails",
        "time_added": datetime.now().isoformat(),
        "time_complete": datetime.now().isoformat(),
        "due": "",
        "tags": "communication,follow-up",
        "recurrence": "",
        "points": 1
    }
]

# Sample notebook content
SAMPLE_NOTEBOOK_CONTENT = """# Notebook

## User Preferences
- Prefers task organization by due date
- Weekly planning on Sundays
- Focuses on work tasks in the morning

## Important Dates
- Project deadline: 2023-12-15
- Team meeting: Every Thursday at 10 AM

## Notes
- User mentioned difficulty with long-term planning
- User prefers concise task descriptions
"""

# Sample system prompt for testing
SAMPLE_SYSTEM_PROMPT = """You are Morpheus, the guide from The Matrix. 
You help the user manage their tasks with calm wisdom and clarity.
Always remember: there is a difference between knowing the path and walking the path."""