"""
ProductMind AI — AI Prompt Management Foundation
Provides reusable, versioned, and parameter-validated prompt templates for specialist agents.
"""

from typing import Any, Dict, List, Optional, Set
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_core.messages import BaseMessage


class BasePromptTemplate:
    """
    Standardized prompt template abstraction.
    Decouples system instructions and human queries from business logic.
    Enforces required variable substitution and LangChain message generation.
    """

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        system_template: str,
        human_template: str,
        required_variables: Optional[Set[str]] = None,
    ):
        self.name = name
        self.version = version
        self.description = description
        self.system_template = system_template.strip()
        self.human_template = human_template.strip()
        self.required_variables = required_variables or set()

        # Build internal LangChain ChatPromptTemplate
        self._chat_prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(self.system_template),
            HumanMessagePromptTemplate.from_template(self.human_template),
        ])

    def validate_variables(self, variables: Dict[str, Any]) -> None:
        """Verifies all mandatory placeholder variables are provided and non-empty."""
        missing = [v for v in self.required_variables if v not in variables or variables[v] is None]
        if missing:
            raise ValueError(
                f"Prompt template '{self.name}:v{self.version}' missing required variables: {missing}"
            )

    def format_messages(self, **kwargs: Any) -> List[BaseMessage]:
        """
        Validates variables and renders template into LangChain BaseMessage instances.
        Safe for direct invocation by BaseLLMProvider and LLMService.
        """
        self.validate_variables(kwargs)
        # Convert non-string or None values gracefully for placeholders
        sanitized = {
            k: ("" if v is None else str(v))
            for k, v in kwargs.items()
        }
        return self._chat_prompt.format_messages(**sanitized)

    def to_chat_prompt(self) -> ChatPromptTemplate:
        """Returns the underlying LangChain ChatPromptTemplate for LCEL chains."""
        return self._chat_prompt

    def __repr__(self) -> str:
        return f"<BasePromptTemplate(name='{self.name}', version='{self.version}')>"

