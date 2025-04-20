# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Commands
- Run application: `uv run python morpheus.py`
- Install MCP Run Python server: `deno run -N -R=node_modules -W=node_modules --node-modules-dir=auto jsr:@pydantic/mcp-run-python warmup`
- Package management: Use `uv` for Python dependencies

## Code Style Guidelines
- Use Python type hints for all function parameters and return values
- Import order: standard library → third-party → local modules
- Error handling: Use try/except blocks with specific exceptions
- Logging: Use the established logging pattern with appropriate log levels
- Prefer f-strings for string formatting
- Use docstrings for classes and functions (multi-line with args/returns)
- Follow PEP 8 naming conventions:
  - snake_case for variables and functions
  - CamelCase for classes
  - UPPERCASE for constants
- Database interactions should be through prepared statements with query logging
- All SQL queries must be audited via the logging system
- Async/await should be used consistently throughout the codebase