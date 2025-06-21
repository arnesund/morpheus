import logging
import os
from typing import Optional, Any

from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.mcp import MCPServerStdio

class CodingAgent:
    """
    CodingAgent provides a specialized agent for handling coding tasks using Claude.
    It uses Claude's MCP server capabilities for executing code-related tasks.
    """
    
    def __init__(self, system_prompt: Optional[str] = None):
        """
        Initialize the CodingAgent with an optional custom system prompt.
        
        Args:
            system_prompt: Custom system prompt for the agent. If None, a default prompt is used.
        """
        load_dotenv()
        self.log_dir = "logs"
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Set up logger
        self.logger = logging.getLogger("coding_agent")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.FileHandler(f"{self.log_dir}/coding_agent.log")
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            self.logger.addHandler(handler)
        
        # Set up Claude MCP server with Bedrock credentials
        claude_env = {
            "CLAUDE_CODE_USE_BEDROCK": "1",
            "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
            "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
            "AWS_REGION": os.getenv("AWS_REGION")
        }
        
        # Create Claude MCP server
        self.claude_mcp_server = MCPServerStdio(
            "claude",
            args=["mcp", "serve"],
            env=claude_env
        )
        
        # Use Claude models
        self.claude_model = AnthropicModel("claude-3-5-sonnet-latest")
        
        # Default system prompt for coding tasks if none is provided
        default_system_prompt = """
        You are an expert software engineer and coding assistant. Your primary goal is to help users 
        with coding tasks, debugging, and software development. You have access to tools that can 
        modify and interact with the codebase.
        
        When working on coding tasks:
        1. Understand the requirements carefully
        2. Break down complex tasks into smaller steps
        3. Write clean, maintainable, and efficient code
        4. Provide regular updates on your progress
        5. Test your solution when possible
        
        Always follow best practices for the programming language you're working with.
        """
        
        # Initialize the agent with the given system prompt
        self.agent = Agent(
            model=self.claude_model,
            system_prompt=system_prompt or default_system_prompt,
            mcp_servers=[self.claude_mcp_server],
        )
    
    async def process_query(self, text: str, history=None):
        """
        Process a coding query and return a streaming result that can be used for updates.
        
        Args:
            text: The coding query or task to process
            history: Optional message history for context
            
        Returns:
            An AsyncRunResult that can be used to stream updates
        """
        self.logger.info(f"Processing coding query: {text[:100]}...")
        async with self.agent.run_mcp_servers():
            return await self.agent.run_stream(text, message_history=history or [])
    
    def extract_update_message(self, message: Any) -> str:
        """
        Extract a user-friendly update message from a Message object.
        
        Args:
            message: The Message object from the agent
            
        Returns:
            A formatted string with the update
        """
        # Extract just the text parts for updates
        parts = []
        for part in message.parts:
            if hasattr(part, "content") and part.content:
                parts.append(part.content)
        
        return "\n".join(parts)

async def get_coding_agent() -> CodingAgent:
    """
    Factory function to get a CodingAgent instance.
    """
    return CodingAgent()