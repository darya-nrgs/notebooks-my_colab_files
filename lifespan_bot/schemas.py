from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class AssistantQuestion(BaseModel):
    kind: Literal["question"]
    question: str = Field(min_length=1)
    choices: Optional[List[str]] = None


class AssistantFinal(BaseModel):
    kind: Literal["final"]
    lifespanEstimate: float
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: Optional[str] = None
    advice: Optional[str] = None


AssistantResponse = AssistantQuestion | AssistantFinal
