"""Company AI Pydantic Schemas for Verified Result Contract, Chat APIs, and Local AI Status.
"""

from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field, field_validator
from backend.app.schemas.department import DepartmentEnum
from backend.app.schemas.security import UserRoleEnum


def normalize_sources(sources: Any) -> List[Dict[str, Any]]:
    """Converts legacy string sources or varied source formats into valid source dictionaries
    matching CompanyAIChatResponse schema: List[Dict[str, Any]].
    Preserves real source information from uploaded files, project files, RAG, and generated files.
    """
    if not sources:
        return []

    if isinstance(sources, (str, dict)):
        raw_list = [sources]
    elif isinstance(sources, (list, tuple, set)):
        raw_list = list(sources)
    else:
        return []

    normalized: List[Dict[str, Any]] = []
    for item in raw_list:
        if isinstance(item, dict):
            entry = dict(item)
            ref_name = entry.get("name") or entry.get("title") or entry.get("doc_id") or entry.get("filename") or ""
            if "name" not in entry and ref_name:
                entry["name"] = str(ref_name)
            if "title" not in entry and ref_name:
                entry["title"] = str(ref_name)
            if "doc_id" not in entry and ref_name:
                entry["doc_id"] = str(ref_name)
            if "type" not in entry:
                entry["type"] = "file"
            normalized.append(entry)
        elif isinstance(item, str):
            clean_str = item.strip()
            if clean_str:
                normalized.append({
                    "name": clean_str,
                    "title": clean_str,
                    "doc_id": clean_str,
                    "type": "file"
                })
        elif item is not None:
            clean_str = str(item).strip()
            if clean_str:
                normalized.append({
                    "name": clean_str,
                    "title": clean_str,
                    "doc_id": clean_str,
                    "type": "file"
                })
    return normalized


class StructuredRequest(BaseModel):
    """Contract produced by Qwen Input Understanding layer.
    Represents a normalised, structured interpretation of a raw user message.
    Consumed by MYGPT orchestrator to select capabilities and tools.
    """
    capability: str = Field(default="GENERAL", description="Target capability: GENERAL | REASONING_MATH | CODING | VISION | EXCEL_DATA | DOCUMENT | RAG | MULTI_MODAL | PROJECT | TOOL")
    operation: Optional[str] = Field(default=None, description="Understood operation e.g. comparison, calculation, planning, generate, debug, overview")
    task_type: Optional[str] = Field(default=None, description="Specific task archetype e.g. GENERAL_QA, PROJECT_PLANNING, CODE_GENERATION, EXCEL_COMPARISON")
    user_request: Optional[str] = Field(default=None, description="Original or cleaned user request prompt")
    intent: str = Field(default="general_question", description="Specific intent identifier e.g. general_question, code_generation, excel_compare")
    action: str = Field(
        default="QUERY",
        description="High-level action: QUERY | CREATE | EXPORT | CALCULATE | COMPARE | DIAGNOSE | SEARCH | EXPAND | MODIFY | PLAN"
    )
    entities: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted entities and parameters"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Specific parameters for deterministic tool execution"
    )
    files: List[str] = Field(
        default_factory=list,
        description="Referenced or uploaded filenames"
    )
    active_document: Optional[Union[str, Dict[str, Any]]] = Field(
        default=None,
        description="Currently active document name, ID, or metadata dict"
    )
    project_context_required: bool = Field(
        default=False,
        description="Whether this request requires inspecting actual project codebase"
    )
    tool_required: Optional[str] = Field(
        default=None,
        description="Specific deterministic tool required e.g. calculator, excel_engine, project_inspector"
    )
    specialist_model: Optional[str] = Field(
        default=None,
        description="Target specialist model identifier e.g. qwen3-4b, qwen2.5-coder-3b, qwen2-vl-2b"
    )
    requires_plan: bool = Field(
        default=False,
        description="True for large project/system building requests requiring planning mode before coding"
    )
    language: Optional[str] = Field(
        default=None,
        description="Programming language if applicable e.g. php, python, typescript"
    )
    framework: Optional[str] = Field(
        default=None,
        description="Framework if applicable e.g. codeigniter3, react, fastapi"
    )
    confidence: float = Field(default=0.80, ge=0.0, le=1.0, description="NLU parse confidence")
    normalized_message: str = Field(
        default="",
        description="Clean English restatement of the user request (informal language resolved)"
    )
    source: str = Field(
        default="regex",
        description="How this request was structured: regex | qwen_nlp | hybrid | fast_path"
    )
    is_follow_up: bool = Field(
        default=False,
        description="Whether this request is a contextual continuation/follow-up to previous turns"
    )
    referenced_previous_topic: Optional[str] = Field(
        default=None,
        description="Prior conversation topic referenced by this request"
    )
    conversation_references: Dict[str, Any] = Field(
        default_factory=dict,
        description="Resolved contextual references from dialogue history"
    )
    target_action: Optional[str] = Field(
        default=None,
        description="Granular intent action: e.g. EXPAND, EXPORT, MODIFY, CALCULATE, CONFIRM"
    )
    target_concept: Optional[str] = Field(
        default=None,
        description="Target semantic concept e.g. phone, transaction_mode, amount"
    )
    filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted filter criteria e.g. {'mode': 'UPI'}"
    )
    target_columns: List[str] = Field(
        default_factory=list,
        description="Target column candidates resolved from semantic understanding"
    )
    group_by: Optional[str] = Field(
        default=None,
        description="Grouping dimension or concept e.g. month, year, day, mode, owner, region"
    )
    source_documents: List[str] = Field(
        default_factory=list,
        description="Referenced or active document identifiers"
    )
    output_format: Optional[str] = Field(
        default=None,
        description="Requested output format: XLSX | DOCX | PDF | JSON | TEXT"
    )
    target: Optional[str] = Field(
        default=None,
        description="Target entity, topic, or document"
    )
    requires_context: bool = Field(
        default=False,
        description="Whether conversation context is genuinely required"
    )
    requires_tool: bool = Field(
        default=False,
        description="Whether a deterministic tool or engine is required"
    )
    department: Optional[str] = Field(
        default=None,
        exclude=True,
        description="[DEPRECATED] Not used in routing or NLU."
    )



class ConversationState(BaseModel):
    """Stateful dialogue context maintained across conversation turns for a session.
    Used to resolve follow-ups and track tasks, code documents, and generated files.
    Does NOT trap user in rigid departments.
    """
    conversation_id: str = Field(..., description="Session / conversation unique identifier")
    capability: Optional[str] = Field(default="GENERAL", description="Active capability domain e.g. GENERAL, CODING, EXCEL_DATA")
    last_capability: Optional[str] = Field(default=None, description="Most recent capability executed")
    department: Optional[str] = Field(default=None, description="Legacy department compatibility context")
    last_department: Optional[str] = Field(default=None, description="Most recent department executed")
    last_intent: Optional[str] = Field(default=None, description="Most recent intent executed")
    last_action: Optional[str] = Field(default=None, description="Most recent action performed")
    last_topic: Optional[str] = Field(default=None, description="Subject of the current conversation thread")
    topic: Optional[str] = Field(default=None, description="Active topic name or description")
    project: Optional[str] = Field(default=None, description="Active project name or identifier")
    task: Optional[str] = Field(default=None, description="Active task name or goal")
    workflow: Optional[str] = Field(default=None, description="Active workflow description or sequence")
    current_module: Optional[str] = Field(default=None, description="Current active module being discussed/implemented")
    current_stage: Optional[str] = Field(default=None, description="Current active stage in workflow")
    conversation_mode: str = Field(default="standard", description="standard | continuation | document_analysis")
    last_entities: Dict[str, Any] = Field(default_factory=dict, description="Merged entity dictionary from prior turns")
    last_normalized_message: Optional[str] = Field(default=None, description="Previous normalized user request")
    last_verified_result: Optional[Dict[str, Any]] = Field(default=None, description="Metadata summary of last result")
    last_generated_file: Optional[str] = Field(default=None, description="Filename of most recent document generated")
    last_file_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata of generated document")
    active_document: Optional[Dict[str, Any]] = Field(default=None, description="Currently active uploaded/generated document descriptor")
    active_document_id: Optional[str] = Field(default=None, description="ID of currently active document")

    def get_task_state(self) -> Dict[str, Any]:
        """Returns structured active task state for context continuation."""
        return {
            "topic": self.topic or self.last_topic,
            "project": self.project,
            "task": self.task,
            "workflow": self.workflow,
            "current_module": self.current_module,
            "current_stage": self.current_stage,
            "pending_action": self.pending_action,
            "active_document": self.active_document,
            "conversation_mode": self.conversation_mode
        }

    @property
    def active_topic(self) -> Optional[str]:
        return self.topic or self.last_topic

    @property
    def active_task(self) -> Optional[str]:
        return self.task

    @property
    def active_capability(self) -> Optional[str]:
        return self.capability

    @property
    def active_operation(self) -> Optional[str]:
        return self.last_operation

    @property
    def active_project(self) -> Optional[str]:
        return self.project

    active_document_ids: List[str] = Field(default_factory=list, description="IDs of all active documents in session")
    active_documents: List[Dict[str, Any]] = Field(default_factory=list, description="List of all active document descriptors in session")
    active_document_name: Optional[str] = Field(default=None, description="Filename of currently active document")
    active_document_type: Optional[str] = Field(default=None, description="Type classification: RESUME | INVOICE | OFFER_LETTER | OFFER_LETTER_TEMPLATE | HR_POLICY | EXPENSE_REPORT | CODE | IMAGE | GENERAL_DOCUMENT")
    active_code_document: Optional[Dict[str, Any]] = Field(default=None, description="Currently active code document descriptor")
    active_code_filename: Optional[str] = Field(default=None, description="Filename of currently active code document")
    active_code_language: Optional[str] = Field(default=None, description="Programming language of currently active code document")
    previous_document: Optional[Dict[str, Any]] = Field(default=None, description="Previous document descriptor for comparisons")
    conversation_documents: List[Dict[str, Any]] = Field(default_factory=list, description="All documents attached or generated in session")
    documents: List[Dict[str, Any]] = Field(default_factory=list, description="Multi-document registry for session")
    selected_document_ids: List[str] = Field(default_factory=list, description="IDs of documents currently selected for multi-file operations")
    last_excel_result: Optional[Dict[str, Any]] = Field(default=None, description="Last computed Excel analytics result")
    last_comparison_result: Optional[Dict[str, Any]] = Field(default=None, description="Last two-file reconciliation analysis result")
    last_comparison_documents: List[Dict[str, Any]] = Field(default_factory=list, description="Documents involved in last comparison")
    last_generated_file_id: Optional[str] = Field(default=None, description="File ID of most recent generated spreadsheet")
    last_operation: Optional[str] = Field(default=None, description="Last executed analytical operation")
    last_metric: Optional[str] = Field(default=None, description="Last computed metric name or title")
    last_result: Optional[Any] = Field(default=None, description="Last computed result data or value")
    last_result_type: Optional[str] = Field(default=None, description="Type of last result: METRIC | TABLE | FILE | COMPARISON | EXPORT")
    last_target_column: Optional[str] = Field(default=None, description="Last targeted column name")
    last_target_columns: List[str] = Field(default_factory=list, description="Last targeted column names")
    last_filters: Dict[str, Any] = Field(default_factory=dict, description="Last applied filter criteria e.g. {'mode': 'UPI'}")
    last_findings: List[str] = Field(default_factory=list, description="Verified findings list from last turn")
    last_exportable_rows: List[Dict[str, Any]] = Field(default_factory=list, description="Last filtered or exportable row dictionaries")
    last_exportable_result: Optional[Dict[str, Any]] = Field(default=None, description="Last exportable dataset/filter result")
    pending_action: Optional[str] = Field(default=None, description="Ongoing multi-step action (e.g. awaiting_error_details)")
    pending_question: Optional[str] = Field(default=None, description="Question asked to user that awaits response")
    pending_clarification: Optional[Dict[str, Any]] = Field(default=None, description="Pending clarification state descriptor")
    is_follow_up: bool = Field(default=False, description="Whether current turn is a follow-up")
    turn_count: int = Field(default=0, description="Total turns in this session")



class CompanyAIResult(BaseModel):
    """Authoritative internal contract produced by MYGPT business engine,
    RAG retrieval, deterministic tools, and permission validation.
    Only authorized safe information enters this contract before being handed to Qwen.
    """
    success: bool = Field(default=True, description="Whether the business task succeeded")
    capability: str = Field(default="GENERAL", description="Primary capability domain executed")
    department: Optional[DepartmentEnum] = Field(default=DepartmentEnum.GENERAL, description="Legacy department compatibility field")
    intent: str = Field(..., description="Classified intent identifier")
    task: str = Field(default="", description="Descriptive task title")
    summary: str = Field(default="", description="High-level factual summary")
    findings: List[str] = Field(default_factory=list, description="Verified findings and data points")
    evidence: List[str] = Field(default_factory=list, description="Direct supporting facts or source quotes")
    retrieved_context: List[Dict[str, Any]] = Field(default_factory=list, description="Authorized RAG chunks")
    actions_taken: List[str] = Field(default_factory=list, description="Deterministic actions executed by MYGPT")
    tool_results: Dict[str, Any] = Field(default_factory=dict, description="Output from deterministic tools")
    warnings: List[str] = Field(default_factory=list, description="Safety or compliance notices")
    citations: List[str] = Field(default_factory=list, description="Source documents referenced")
    confidence: float = Field(default=0.90, ge=0.0, le=1.0, description="Routing/reasoning confidence score")
    permission_status: str = Field(default="AUTHORIZED", description="Permission evaluation result")
    requires_approval: bool = Field(default=False, description="Whether the planned action requires human approval")
    files: List[Dict[str, Any]] = Field(default_factory=list, description="Generated documents or attachments")
    pending_action: Optional[str] = Field(default=None, description="Optional pending action to store in conversation context")
    pending_clarification: Optional[Dict[str, Any]] = Field(default=None, description="Optional pending clarification state")
    user_facing_result: Optional[str] = Field(default=None, description="Clean user-facing response text")
    internal_metadata: Dict[str, Any] = Field(default_factory=dict, description="Diagnostics only visible in developer mode")


class CompanyAIChatRequest(BaseModel):
    """Public user request schema."""
    message: str = Field(..., min_length=1, description="Natural language user request")
    conversation_id: Optional[str] = Field(default=None, description="Canonical conversation unique identifier")
    session_id: Optional[str] = Field(default=None, description="Legacy session ID alias")
    document_id: Optional[str] = Field(default=None, description="Canonical attached document identifier")
    attached_doc_id: Optional[str] = Field(default=None, description="Legacy attached document ID alias")
    attached_file_id: Optional[str] = Field(default=None, description="Legacy attached file ID alias")
    attached_document_id: Optional[str] = Field(default=None, description="Legacy attached document ID alias")
    active_document_ids: Optional[List[str]] = Field(default_factory=list, description="IDs of currently active documents")
    user_id: Optional[str] = Field(default="dev_employee", description="Requesting user identifier")
    user_role: Optional[UserRoleEnum] = Field(default=UserRoleEnum.EMPLOYEE, description="User RBAC role")
    capability_override: Optional[str] = Field(default=None, description="Optional capability hint")
    department_override: Optional[DepartmentEnum] = Field(default=None, description="Optional manual department hint")

    def get_canonical_conversation_id(self) -> str:
        return self.conversation_id or self.session_id or "default_session"

    def get_canonical_document_id(self) -> Optional[str]:
        return (
            self.document_id
            or self.attached_doc_id
            or self.attached_file_id
            or self.attached_document_id
            or None
        )



class CompanyAIChatResponse(BaseModel):
    """User-facing response payload."""
    answer: str = Field(..., description="Natural language explanation formatted by Qwen")
    answer_type: Optional[str] = Field(default="chat", description="Format classification: chat | comparison | calculation | summary | excel_analysis | code | error_debug | vision")
    structured_data: Optional[Dict[str, Any]] = Field(default=None, description="Clean separated structured payload for UI card renderers")
    active_document: Optional[str] = Field(default=None, description="Name of currently active document")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Safe runtime metadata")
    capability: Optional[str] = Field(default="GENERAL", description="Capability executed")
    department: str = Field(default="GENERAL", description="[Deprecated] Kept purely for backward compatibility")
    intent: str = Field(..., description="Classified intent")
    status: str = Field(default="success", description="Execution status")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Citations and referenced documents")
    actions: List[str] = Field(default_factory=list, description="Actions and tools executed")
    files: List[Dict[str, Any]] = Field(default_factory=list, description="Downloadable files")
    requires_approval: bool = Field(default=False, description="Human approval flag")
    confidence: float = Field(default=0.90, description="Routing confidence score")
    execution_steps: List[str] = Field(default_factory=list, description="Non-sensitive workflow steps executed")
    tool_results: Dict[str, Any] = Field(default_factory=dict, description="Structured tool results for rich UI card rendering")

    @field_validator("sources", mode="before")
    @classmethod
    def validate_sources(cls, v: Any) -> List[Dict[str, Any]]:
        return normalize_sources(v)


class RenameConversationRequest(BaseModel):
    """Request payload for renaming a conversation."""
    title: str = Field(..., min_length=1, max_length=100, description="New meaningful conversation title")


class AIStatusResponse(BaseModel):
    """Safe system status reporting for local AI health indicator."""
    company_ai: str = "online"
    mygpt: str = "available"
    answer_model: str = "Gemma-4-E2B-It-Q4_K_M"
    answer_model_status: str = "available"
    coding_model_status: str = "available"
    vision_model_status: str = "available"
    models: Optional[Dict[str, Any]] = None
    external_ai: bool = False
    device: str = "cpu"
    runtime: str = "llama.cpp"
