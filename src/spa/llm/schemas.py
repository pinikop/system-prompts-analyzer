"""Pydantic models for LLM structured output."""

from typing import Literal

from pydantic import BaseModel, Field


class AssistantAnalysis(BaseModel):
    """LLM-extracted thematic analysis of one coding assistant's system prompt."""

    identity: str = Field(description="1-2 sentence identity statement")
    tone: list[str] = Field(
        description="3-5 tone descriptors, e.g. ['concise', 'direct', 'cautious']",
        min_length=3,
        max_length=5,
    )
    personality: str = Field(description="1-2 sentence personality summary")
    behavioral_rules: list[str] = Field(
        description="5-10 key behavioral rules extracted from the prompt",
        min_length=5,
        max_length=10,
    )
    unique_features: list[str] = Field(
        description="3-5 features that distinguish this coding assistant",
        min_length=3,
        max_length=5,
    )
    coding_philosophy: str = Field(description="1-2 sentence summary of coding approach")
    safety_emphasis: Literal["low", "medium", "high", "very_high"] = Field(
        description="Overall level of safety emphasis in the prompt"
    )
    safety_details: str = Field(description="1-2 sentence description of safety approach")
    autonomy_level: Literal["low", "medium", "high"] = Field(
        description="How independently the assistant acts without asking the user"
    )
    error_handling: str = Field(description="1-2 sentence approach to errors")
