"""Security, Role, and Permission Pydantic schemas for Company AI.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class SecurityLevelEnum(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    RESTRICTED = "RESTRICTED"
    CONFIDENTIAL = "CONFIDENTIAL"


class UserRoleEnum(str, Enum):
    EMPLOYEE = "EMPLOYEE"
    HR_MANAGER = "HR_MANAGER"
    FINANCE_MANAGER = "FINANCE_MANAGER"
    TECH_ADMIN = "TECH_ADMIN"
    ADMIN = "ADMIN"


class DocumentMetadata(BaseModel):
    document_id: str
    filename: str
    department: str
    document_type: str = "general"
    security_level: SecurityLevelEnum = SecurityLevelEnum.INTERNAL
    role_required: List[UserRoleEnum] = Field(default_factory=lambda: [UserRoleEnum.EMPLOYEE])
    source: str = "local"
    created_at: float
    updated_at: float


class AuditRecord(BaseModel):
    audit_id: str
    timestamp: str
    user_id: str
    user_role: str
    department: str
    requested_resource: str
    operation: str
    access_allowed: bool
    details: Dict[str, Any] = Field(default_factory=dict)


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    department: str = Field(..., description="Target department (TECH, HR, FINANCE, GENERAL)")
    user_role: Optional[UserRoleEnum] = Field(default=UserRoleEnum.EMPLOYEE, description="User role context")
    user_id: Optional[str] = Field(default="dev_user", description="Requesting user identifier")
    top_k: int = Field(default=3, ge=1, le=10)
