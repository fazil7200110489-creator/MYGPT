"""Pydantic schemas for Company AI Department Registry and Intent Routing.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator


class DepartmentEnum(str, Enum):
    TECH = "TECH"
    HR = "HR"
    FINANCE = "FINANCE"
    GENERAL = "GENERAL"


class RoutingDecision(BaseModel):
    department: DepartmentEnum = Field(..., description="Target company department")
    intent: str = Field(..., description="Identified specific intent")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0")
    knowledge_base: str = Field(..., description="Target knowledge base identifier")
    required_tools: List[str] = Field(default_factory=list, description="List of tool identifiers needed for the intent")
    requires_permission: bool = Field(default=False, description="Whether this action/intent requires privileged authorization")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Extracted parameters and key entities")

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"Confidence score must be between 0.0 and 1.0, got {v}")
        return round(v, 4)


class RouteRequest(BaseModel):
    message: str = Field(..., description="Natural language user request message", min_length=1)
    user_id: Optional[str] = Field(default=None, description="Optional user ID for role/permission checking")
    role: Optional[str] = Field(default="employee", description="User role in the organization")
    session_id: Optional[str] = Field(default=None, description="Optional session tracking ID")


class DepartmentInfo(BaseModel):
    department: DepartmentEnum
    name: str
    description: str
    knowledge_base: str
    supported_intents: List[str]
    available_tools: List[str]
    default_permission_required: bool = False
