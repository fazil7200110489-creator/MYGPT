"""Company AI Pydantic Schemas for Verified Result Contract, Chat APIs, and Local AI Status.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from backend.app.schemas.department import DepartmentEnum
from backend.app.schemas.security import UserRoleEnum


class StructuredRequest(BaseModel):
    """Contract produced by Qwen Input Understanding layer.
    Represents a normalised, structured interpretation of a raw user message.
    Consumed by MYGPT routing & department workflows.
    Qwen must NOT perform RBAC, access data, or execute tools here — it only produces this schema.
    """
    department: str = Field(..., description="Resolved department: HR | FINANCE | TECH | GENERAL")
    intent: str = Field(..., description="Specific intent identifier e.g. policy_question, document_export")
    action: str = Field(
        default="QUERY",
        description="High-level action: QUERY | CREATE | EXPORT | CALCULATE | COMPARE | DIAGNOSE | SEARCH | EXPAND | MODIFY"
    )
    entities: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted entities: output_format, amounts, leave_type, candidate_name, period, status_code, file_operation"
    )
    normalized_message: str = Field(
        default="",
        description="Clean English restatement of the user request (informal language resolved)"
    )
    confidence: float = Field(default=0.80, ge=0.0, le=1.0, description="NLP parse confidence")
    source: str = Field(
        default="regex",
        description="How this request was structured: regex | qwen_nlp | hybrid"
    )
    is_follow_up: bool = Field(
        default=False,
        description="Whether this request is a contextual continuation/follow-up to previous turns"
    )
    referenced_previous_topic: Optional[str] = Field(
        default=None,
        description="Prior conversation topic referenced by this request (e.g. 'HR casual leave policy')"
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
    operation: Optional[str] = Field(
        default=None,
        description="Understood analytical operation e.g. UNIQUE_VALUES, FILTER_EXPORT, COLUMN_EXPORT, SUM, COUNT"
    )
    target_columns: List[str] = Field(
        default_factory=list,
        description="Target column candidates resolved from semantic understanding"
    )


class ConversationState(BaseModel):
    """Stateful dialogue context maintained across conversation turns for a session.
    Used to resolve follow-ups, maintain department steering, and track document generation and uploads.
    Does NOT bypass or grant RBAC permissions.
    """
    conversation_id: str = Field(..., description="Session / conversation unique identifier")
    department: Optional[str] = Field(default=None, description="Active department context e.g. TECH, HR, FINANCE")
    last_department: Optional[str] = Field(default=None, description="Most recent department executed")
    last_intent: Optional[str] = Field(default=None, description="Most recent intent executed")
    last_action: Optional[str] = Field(default=None, description="Most recent action performed")
    last_topic: Optional[str] = Field(default=None, description="Subject of the current conversation thread")
    last_entities: Dict[str, Any] = Field(default_factory=dict, description="Merged entity dictionary from prior turns")
    last_normalized_message: Optional[str] = Field(default=None, description="Previous normalized user request")
    last_verified_result: Optional[Dict[str, Any]] = Field(default=None, description="Metadata summary of last result")
    last_generated_file: Optional[str] = Field(default=None, description="Filename of most recent document generated")
    last_file_metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata of generated document")
    active_document: Optional[Dict[str, Any]] = Field(default=None, description="Currently active uploaded/generated document descriptor")
    active_document_id: Optional[str] = Field(default=None, description="ID of currently active document")
    active_document_ids: List[str] = Field(default_factory=list, description="IDs of all active documents in session")
    active_documents: List[Dict[str, Any]] = Field(default_factory=list, description="List of all active document descriptors in session")
    active_document_name: Optional[str] = Field(default=None, description="Filename of currently active document")
    active_document_type: Optional[str] = Field(default=None, description="Type classification: RESUME | INVOICE | OFFER_LETTER | OFFER_LETTER_TEMPLATE | HR_POLICY | EXPENSE_REPORT | GENERAL_DOCUMENT")
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
    last_exportable_rows: List[Dict[str, Any]] = Field(default_factory=list, description="Last filtered or exportable row dictionaries")
    last_exportable_result: Optional[Dict[str, Any]] = Field(default=None, description="Last exportable dataset/filter result")
    pending_action: Optional[str] = Field(default=None, description="Ongoing multi-step action (e.g. awaiting_error_details)")
    pending_question: Optional[str] = Field(default=None, description="Question asked to user that awaits response")
    is_follow_up: bool = Field(default=False, description="Whether current turn is a follow-up")
    turn_count: int = Field(default=0, description="Total turns in this session")



class CompanyAIResult(BaseModel):
    """Authoritative internal contract produced by MYGPT business engine,
    RAG retrieval, deterministic tools, and permission validation.
    Only authorized safe information enters this contract before being handed to Qwen.
    """
    success: bool = Field(default=True, description="Whether the business task succeeded")
    department: DepartmentEnum = Field(..., description="Target department (TECH, HR, FINANCE, GENERAL)")
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
    user_id: Optional[str] = Field(default="dev_employee", description="Requesting user identifier")
    user_role: Optional[UserRoleEnum] = Field(default=UserRoleEnum.EMPLOYEE, description="User RBAC role")
    department_override: Optional[DepartmentEnum] = Field(default=None, description="Optional manual department hint")

    def get_canonical_conversation_id(self) -> str:
        return self.conversation_id or self.session_id or "default_session"

    def get_canonical_document_id(self) -> Optional[str]:
        return self.document_id or self.attached_doc_id or self.attached_file_id or self.attached_document_id



class CompanyAIChatResponse(BaseModel):
    """User-facing response payload."""
    answer: str = Field(..., description="Natural language explanation formatted by Qwen")
    department: str = Field(..., description="Routed department name")
    intent: str = Field(..., description="Classified intent")
    status: str = Field(default="success", description="Execution status")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Citations and referenced documents")
    actions: List[str] = Field(default_factory=list, description="Actions and tools executed")
    files: List[Dict[str, Any]] = Field(default_factory=list, description="Downloadable files")
    requires_approval: bool = Field(default=False, description="Human approval flag")
    confidence: float = Field(default=0.90, description="Routing confidence score")
    execution_steps: List[str] = Field(default_factory=list, description="Non-sensitive workflow steps executed")
    tool_results: Dict[str, Any] = Field(default_factory=dict, description="Structured tool results for rich UI card rendering")


class AIStatusResponse(BaseModel):
    """Safe system status reporting for local AI health indicator."""
    company_ai: str = "online"
    mygpt: str = "available"
    answer_model: str = "Qwen3-4B-Q4_K_M"
    answer_model_status: str = "available"
    external_ai: bool = False
    device: str = "cpu"
    runtime: str = "llama.cpp"
