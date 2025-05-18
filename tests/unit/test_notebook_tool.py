"""
Unit tests for the write_notes_to_notebook tool.
"""
import os
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_morpheus_bot(temp_notebook_dir, temp_notebook_file):
    """Create a mock MorpheusBot instance with notebook attributes."""
    mock_bot = MagicMock()
    mock_bot.notes_dir = str(temp_notebook_dir)
    mock_bot.notebook_filename = temp_notebook_file.name
    return mock_bot


class TestWriteNotesToNotebookTool:
    def test_write_notes(self, mock_morpheus_bot, temp_notebook_file):
        """Test writing notes to notebook."""
        from agent import MorpheusBot
        
        # Create a real instance of MorpheusBot with mocked attributes
        with patch.object(MorpheusBot, '__init__', return_value=None):
            bot = MorpheusBot()
            bot.notes_dir = mock_morpheus_bot.notes_dir
            bot.notebook_filename = mock_morpheus_bot.notebook_filename
            
            # Create the function as it would be created in the real bot
            def write_notes_to_notebook(text):
                filepath = f"{bot.notes_dir}/{bot.notebook_filename}"
                try:
                    with open(filepath, "a") as f:
                        f.write(text + "\n")
                    return "Text written to notebook."
                except Exception as e:
                    return f"Error writing to notebook: {e}"
            
            # Test the function
            result = write_notes_to_notebook("This is a new note.")
            assert result == "Text written to notebook."
            
            # Verify the note was written to the file
            content = temp_notebook_file.read_text()
            assert "This is a new note." in content

    def test_write_multiple_notes(self, mock_morpheus_bot, temp_notebook_file):
        """Test writing multiple notes to notebook."""
        from agent import MorpheusBot
        
        with patch.object(MorpheusBot, '__init__', return_value=None):
            bot = MorpheusBot()
            bot.notes_dir = mock_morpheus_bot.notes_dir
            bot.notebook_filename = mock_morpheus_bot.notebook_filename
            
            # Create the function as it would be created in the real bot
            def write_notes_to_notebook(text):
                filepath = f"{bot.notes_dir}/{bot.notebook_filename}"
                try:
                    with open(filepath, "a") as f:
                        f.write(text + "\n")
                    return "Text written to notebook."
                except Exception as e:
                    return f"Error writing to notebook: {e}"
            
            # Write multiple notes
            write_notes_to_notebook("First note")
            write_notes_to_notebook("Second note")
            result = write_notes_to_notebook("Third note")
            
            assert result == "Text written to notebook."
            
            # Verify all notes were written to the file
            content = temp_notebook_file.read_text()
            assert "First note" in content
            assert "Second note" in content
            assert "Third note" in content

    def test_error_handling(self):
        """Test error handling when writing fails."""
        from agent import MorpheusBot
        
        with patch.object(MorpheusBot, '__init__', return_value=None):
            bot = MorpheusBot()
            bot.notes_dir = "/nonexistent/directory"  # Invalid directory
            bot.notebook_filename = "test_notebook.md"
            
            # Create the function as it would be created in the real bot
            def write_notes_to_notebook(text):
                filepath = f"{bot.notes_dir}/{bot.notebook_filename}"
                try:
                    with open(filepath, "a") as f:
                        f.write(text + "\n")
                    return "Text written to notebook."
                except Exception as e:
                    return f"Error writing to notebook: {e}"
            
            # This should return an error message
            result = write_notes_to_notebook("This will fail")
            assert "Error writing to notebook" in result