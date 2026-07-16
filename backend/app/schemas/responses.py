"""Pydantic schemas for MyGPT Studio requests and responses validation.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class DashboardResponse(BaseModel):
    model_name: str
    version: str
    device: str
    is_training: bool
    vocab_size: int
    embedding_dim: int
    num_layers: int
    num_heads: int
    context_len: int
    current_epoch: int
    current_step: int
    total_params: int


class ModelInfoResponse(BaseModel):
    model_name: str
    version: str
    total_params: int
    layers_info: List[Dict[str, Any]]


class TokenizerRequest(BaseModel):
    text: str


class DatasetRequest(BaseModel):
    text: str
    seq_len: int
    stride: int = 1


class TokenizerResponse(BaseModel):
    text: str
    tokens: List[str]
    ids: List[int]
    mapping: List[Dict[str, Any]]


class InferenceRequest(BaseModel):
    prompt: str
    max_tokens: int = Field(default=50, ge=1, le=500)
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    top_k: int = Field(default=0, ge=0, le=100)
    top_p: float = Field(default=0.0, ge=0.0, le=1.0)
    stop_tokens: Optional[List[str]] = None


class InferenceResponse(BaseModel):
    prompt: str
    input_ids: List[int]
    output_ids: List[int]
    generated_text: str


class TrainingRequest(BaseModel):
    settings: Dict[str, Any]


class TrainingStatusResponse(BaseModel):
    is_training: bool
    current_epoch: int
    current_step: int
    losses: List[Dict[str, Any]]
    val_losses: List[Dict[str, Any]]
    logs: List[str]


class CheckpointResponse(BaseModel):
    filename: str
    epoch: Any
    loss: Any
    size_mb: float
    date: str


class LoadCheckpointRequest(BaseModel):
    filename: str


class AttentionResponse(BaseModel):
    tokens: List[str]
    attention_weights: List[List[List[float]]]  # (num_heads, seq_len, seq_len)


class EmbeddingResponse(BaseModel):
    shape: List[int]
    embeddings: List[Dict[str, Any]]


class ModelConfigRequest(BaseModel):
    max_sequence_length: int = Field(..., ge=16, le=4096)
    embedding_dimension: int = Field(..., ge=16, le=1024)


class ModelConfigResponse(BaseModel):
    max_sequence_length: int
    embedding_dimension: int

