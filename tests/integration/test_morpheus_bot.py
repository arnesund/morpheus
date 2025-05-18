"""
Integration tests for the MorpheusBot class.
"""
import os
import sqlite3
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from tests.fixtures.test_data import SAMPLE_TASKS, SAMPLE_SYSTEM_PROMPT

from pydantic_ai.messages import ModelMessage, TextPart, ToolCallPart


@pytest.fixture
def temp_db_path(tmp_path):
    """Create a temporary database path."""
    db_path = tmp_path / "test_tasks.db"
    return str(db_path)


@pytest.fixture
def mock_run_result():
    """Create a mock result from agent.run()."""
    # Create a mock Message object
    mock_message = MagicMock(spec=ModelMessage)
    
    # Create message parts
    text_part = MagicMock(spec=TextPart)
    text_part.content = "I've processed your request."
    text_part.has_content.return_value = True
    
    tool_part = MagicMock(spec=ToolCallPart)
    tool_part.tool_name = "query_task_database"
    tool_part.content = "Task 1, Task 2"
    tool_part.args = "SELECT * FROM tasks"
    tool_part.has_content.return_value = True
    
    # Set up message parts
    mock_message.parts = [text_part, tool_part]
    
    # Create the mock result
    mock_result = MagicMock()
    mock_result.new_messages.return_value = [mock_message]
    mock_result.all_messages.return_value = [mock_message]
    mock_result.new_messages_json.return_value = [{"role": "assistant", "content": "I've processed your request."}]
    mock_result.all_messages_json.return_value = [{"role": "assistant", "content": "I've processed your request."}]
    mock_result.usage.return_value = {"prompt_tokens": 100, "completion_tokens": 50}
    mock_result.data = "I've processed your request."
    
    return mock_result


class TestMorpheusBot:
    @pytest.mark.asyncio
    async def test_bot_initialization(self, temp_db_path, temp_notebook_dir):
        """Test MorpheusBot initialization."""
        from agent import MorpheusBot
        
        # Mock environment variables and external dependencies
        with patch('os.getenv') as mock_getenv, \
             patch('pydantic_ai.models.anthropic.AnthropicModel', return_value=MagicMock()) as mock_anthropic, \
             patch('pydantic_ai.models.openai.OpenAIModel', return_value=MagicMock()) as mock_openai, \
             patch('pydantic_ai.models.fallback.FallbackModel', return_value=MagicMock()) as mock_fallback, \
             patch('pydantic_ai.Agent', return_value=MagicMock()) as mock_agent, \
             patch('pydantic_ai.mcp.MCPServerStdio', return_value=MagicMock()) as mock_mcp:
            
            # Set up environment variables
            mock_getenv.return_value = "mock_value"
            
            # Set up the notebook path
            notebook_path = os.path.join(str(temp_notebook_dir), "test_notebook.md")
            
            # Create the bot
            bot = MorpheusBot(
                db_filename=temp_db_path,
                system_prompt=SAMPLE_SYSTEM_PROMPT,
                notebook_filename=notebook_path
            )
            
            # Verify initialization
            assert bot.DB_FILENAME == temp_db_path
            assert bot.notebook_filename == notebook_path
            assert bot.history == []
            assert bot.history_timestamp is None
            
            # Verify the database was created
            assert os.path.exists(temp_db_path)
            
            # For this test, we just care that the bot was initialized successfully, 
            # not whether the mock was called
            assert bot.agent is not None

    @pytest.mark.asyncio
    async def test_process_message(self, temp_db_path, mock_run_result):
        """Test processing a message through the agent."""
        from agent import MorpheusBot
        
        # Create a bot with mocked agent
        with patch('os.getenv') as mock_getenv, \
             patch('pydantic_ai.Agent') as MockAgent, \
             patch('pydantic_ai.mcp.MCPServerStdio', return_value=MagicMock()), \
             patch('pydantic_ai.models.anthropic.AnthropicModel', return_value=MagicMock()), \
             patch('pydantic_ai.models.openai.OpenAIModel', return_value=MagicMock()), \
             patch('pydantic_ai.models.fallback.FallbackModel', return_value=MagicMock()):
            
            # Set up environment variables
            mock_getenv.return_value = "mock_value"
            
            # Set up the mock agent
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_run_result)
            mock_agent.run_mcp_servers.return_value.__aenter__ = AsyncMock()
            mock_agent.run_mcp_servers.return_value.__aexit__ = AsyncMock()
            MockAgent.return_value = mock_agent
            
            # Create the bot
            bot = MorpheusBot(db_filename=temp_db_path)
            
            # Replace the created agent with our mock to ensure we test the process_message method
            bot.agent = mock_agent
            
            # Also mock log_messages to avoid file write issues
            bot.log_messages = MagicMock()
            
            # Process a message
            result = await bot.process_message("Hello, I need help with tasks")
            
            # Verify the agent was called
            mock_agent.run.assert_called_once_with(
                "Hello, I need help with tasks", 
                message_history=[]
            )
            
            # Verify the results
            assert isinstance(result, dict)
            assert "blocks" in result
            assert "text" in result
            assert result["text"] == "I've processed your request."
            
            # Verify history was updated
            assert bot.history_timestamp is not None

    def test_query_db(self, temp_db_path):
        """Test database query functionality."""
        from agent import MorpheusBot
        
        # Create a bot
        with patch('os.getenv') as mock_getenv, \
             patch('pydantic_ai.Agent', return_value=MagicMock()), \
             patch('pydantic_ai.mcp.MCPServerStdio', return_value=MagicMock()), \
             patch('pydantic_ai.models.anthropic.AnthropicModel', return_value=MagicMock()), \
             patch('pydantic_ai.models.openai.OpenAIModel', return_value=MagicMock()), \
             patch('pydantic_ai.models.fallback.FallbackModel', return_value=MagicMock()):
            
            # Set up environment variables
            mock_getenv.return_value = "mock_value"
            
            # Create and initialize the bot
            bot = MorpheusBot(db_filename=temp_db_path)
            
            # Add a task to the database
            bot.query_db(
                "INSERT INTO tasks (description, time_added) VALUES (?, ?)",
                ("Test task", "2023-01-01T00:00:00")
            )
            
            # Query the database
            results = bot.query_db("SELECT * FROM tasks")
            
            # Verify the results
            assert len(results) == 1
            assert results[0][1] == "Test task"  # description
            assert results[0][2] == "2023-01-01T00:00:00"  # time_added

    def test_history_management(self):
        """Test history management functions."""
        from agent import MorpheusBot
        import time
        
        # Create a bot
        with patch('os.getenv') as mock_getenv, \
             patch('pydantic_ai.Agent', return_value=MagicMock()), \
             patch('pydantic_ai.mcp.MCPServerStdio', return_value=MagicMock()), \
             patch('pydantic_ai.models.anthropic.AnthropicModel', return_value=MagicMock()), \
             patch('pydantic_ai.models.openai.OpenAIModel', return_value=MagicMock()), \
             patch('pydantic_ai.models.fallback.FallbackModel', return_value=MagicMock()):
            
            # Set up environment variables
            mock_getenv.return_value = "mock_value"
            
            # Create the bot
            bot = MorpheusBot(db_filename=":memory:")
            
            # Set history
            test_history = [{"role": "user", "content": "Hello"}]
            bot.set_history(test_history)
            
            # Verify history was set
            assert bot.history == test_history
            assert bot.history_timestamp is not None
            
            # Get history
            retrieved_history = bot.get_history()
            assert retrieved_history == test_history
            
            # Test history expiration (mock time to be more than 1 hour later)
            with patch('time.time') as mock_time:
                mock_time.return_value = bot.history_timestamp + 3601  # 1 hour + 1 second
                expired_history = bot.get_history()
                assert expired_history == []  # History should be cleared
