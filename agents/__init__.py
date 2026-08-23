"""
MAX OS — Agents Package
"""

from agents.browser_agent import BrowserAgent, browser_agent_executor
from agents.computer_use_agent import ComputerUseAgent, computer_use_agent_executor
from agents.file_agent import FileAgent, file_agent_executor
from agents.registry import AGENT_REGISTRY, AgentDefinition, AgentRegistry
from agents.terminal_agent import TerminalAgent, terminal_agent_executor

__all__ = [
    "BrowserAgent",
    "browser_agent_executor",
    "ComputerUseAgent",
    "computer_use_agent_executor",
    "FileAgent",
    "file_agent_executor",
    "TerminalAgent",
    "terminal_agent_executor",
    "AgentRegistry",
    "AGENT_REGISTRY",
    "AgentDefinition",
]

