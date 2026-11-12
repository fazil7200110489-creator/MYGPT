"""Extensible Capability and Task-Based Schema for MYGPT General-Purpose Architecture.

Replaces department-centric routing with capability-driven processing.
Department fields remain solely as deprecated legacy metadata.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class CapabilityEnum(str, Enum):
    """Primary system capabilities."""
    GENERAL = "GENERAL"
    REASONING_MATH = "REASONING_MATH"
    CODING = "CODING"
    VISION = "VISION"
    EXCEL_DATA = "EXCEL_DATA"
    DOCUMENT = "DOCUMENT"
    RAG = "RAG"
    PROJECT = "PROJECT"
    MULTI_MODAL = "MULTI_MODAL"
    TOOL = "TOOL"


class TaskTypeEnum(str, Enum):
    """Granular task classifications across capabilities."""
    GENERAL_QA = "GENERAL_QA"
    REASONING_MATH = "REASONING_MATH"
    CODE_GENERATION = "CODE_GENERATION"
    CODE_DEBUG = "CODE_DEBUG"
    CODE_REVIEW = "CODE_REVIEW"
    CODE_EXPLANATION = "CODE_EXPLANATION"
    PROJECT_PLANNING = "PROJECT_PLANNING"
    PROJECT_INSPECTION = "PROJECT_INSPECTION"
    EXCEL_COMPARISON = "EXCEL_COMPARISON"
    EXCEL_CALCULATION = "EXCEL_CALCULATION"
    EXCEL_FILTER = "EXCEL_FILTER"
    EXCEL_OVERVIEW = "EXCEL_OVERVIEW"
    DOCUMENT_SUMMARY = "DOCUMENT_SUMMARY"
    DOCUMENT_QA = "DOCUMENT_QA"
    DOCUMENT_EXTRACTION = "DOCUMENT_EXTRACTION"
    IMAGE_INSPECTION = "IMAGE_INSPECTION"
    VISION_CODING = "VISION_CODING"
    TOOL_EXECUTION = "TOOL_EXECUTION"


class CapabilityResult(BaseModel):
    """Standardized result returned by any specialist capability."""
    success: bool = True
    capability: str = Field(default="GENERAL", description="Capability identifier e.g. CODING, EXCEL_DATA")
    operation: str = Field(default="GENERAL_QA", description="Executed operation e.g. comparison, planning")
    task_type: Optional[str] = Field(default=None, description="Granular task type")
    answer: str = Field(default="", description="Human-ready or verified primary answer")
    answer_type: str = Field(default="text", description="Display archetype: text | comparison | calculation | code | plan | error")
    structured_data: Optional[Dict[str, Any]] = Field(default=None, description="Machine-readable structured payload")
    sources: List[Any] = Field(default_factory=list, description="Ground truth citations, files, or references")
    files: List[str] = Field(default_factory=list, description="Generated or referenced files")
    requires_plan: bool = Field(default=False, description="Flag indicating system-building planning mode")
    plan: Optional[Dict[str, Any]] = Field(default=None, description="Project plan, architecture breakdown, or step checklist")
    clarification_needed: bool = Field(default=False, description="True if ambiguous input requires user clarification")
    clarification_message: Optional[str] = Field(default=None, description="Clarification prompt for user")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="Execution and verification confidence")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic and execution metadata")
