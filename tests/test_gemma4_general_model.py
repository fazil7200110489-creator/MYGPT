"""Unit tests for Gemma 4 E2B Instruct primary model, automatic Qwen fallback, and recovery."""

from concurrent.futures import ThreadPoolExecutor
import os
import sys
import time
import types
import pytest

from backend.app.core.config import settings
from backend.app.schemas.company_ai import CompanyAIResult
from backend.app.schemas.department import DepartmentEnum
from backend.app.services.llm.qwen_answer_model import QwenAnswerModel
from backend.app.services.llm.model_registry import model_registry, GENERAL_MODEL
from backend.app.services.routing.model_router import model_router


def _write_fake_gguf(path, valid_header: bool = True, size: int = 120_000) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = b"GGUF" if valid_header else b"BAD!"
    with open(path, "wb") as f:
        f.write(prefix)
        f.write(b"\x00" * (size - len(prefix)))
    return str(path)


@pytest.fixture
def isolated_model_env(monkeypatch, tmp_path):
    """Provides isolated GGUF directory and preserves ModelRegistry state after mocked tests."""
    monkeypatch.delenv("MYGPT_GENERAL_MODEL_ROLLBACK", raising=False)
    monkeypatch.delenv("GENERAL_MODEL_PATH", raising=False)
    monkeypatch.setenv("MYGPT_PRIMARY_RECOVERY_COOLDOWN_SEC", "60")
    original_desc = model_registry.get_model(GENERAL_MODEL)
    yield tmp_path
    if original_desc is not None:
        model_registry.register_model(original_desc)


def test_gemma4_is_selected_as_primary_general_model(monkeypatch):
    monkeypatch.delenv("MYGPT_GENERAL_MODEL_ROLLBACK", raising=False)
    monkeypatch.delenv("GENERAL_MODEL_PATH", raising=False)

    model = QwenAnswerModel()
    assert model._is_gemma is True
    assert model.model_name == "Gemma-4-E2B-It-Q4_K_M"
    assert model._model_path is not None
    assert "gemma-4-E2B-it-Q4_K_M.gguf" in model._model_path
    assert model._stop_tokens() == ["<turn|>", "<eos>"]


def test_qwen_rollback_flag_selects_qwen_model(monkeypatch):
    monkeypatch.setenv("MYGPT_GENERAL_MODEL_ROLLBACK", "qwen")
    monkeypatch.delenv("GENERAL_MODEL_PATH", raising=False)

    model = QwenAnswerModel()
    assert model._is_gemma is False
    assert "Qwen" in model.model_name
    assert model._model_path is not None
    assert "qwen2.5-coder-3b-instruct-q4_k_m.gguf" in model._model_path.lower()
    assert model._stop_tokens() == ["<|im_end|>", "<|endoftext|>", "<|im_start|>"]


def test_gemma4_output_cleanup_and_markdown_validation():
    model = QwenAnswerModel()
    raw = "<|channel>thought\ninternal reasoning\n<channel|>Here is the answer.\n---\n- Point 1<turn|>"
    cleaned = model._clean_model_output(raw)
    assert cleaned == "Here is the answer.\n---\n- Point 1"
    assert model._is_valid_natural_language(cleaned) is True
    assert model._is_valid_natural_language("!!!!!@@@@@#####") is False


def test_registry_and_router_expose_gemma4_general_model():
    desc = model_registry.get_model(GENERAL_MODEL)
    assert desc is not None
    if os.path.exists(settings._GEMMA4_GENERAL_PATH) and not os.environ.get("MYGPT_GENERAL_MODEL_ROLLBACK"):
        assert desc.name == "gemma-4-e2b-it"
        decision = model_router.route(query="What is the capital of France?")
        assert decision.capability == "general"
        assert decision.model == "gemma-4-e2b-it"


# ----------------------------------------------------------------------
# 7 Required Fallback, Recovery & Concurrency Scenarios (Mocked Runtime)
# ----------------------------------------------------------------------


def _install_fake_llama(monkeypatch, handler):
    """Installs a fake llama_cpp module whose Llama(**kwargs) returns handler(kwargs)."""
    fake_mod = types.ModuleType("llama_cpp")
    fake_mod.Llama = handler
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_mod)


class _FakeLLMInstance:
    def __init__(self, reply_text: str, fail_on_call: bool = False):
        self.reply_text = reply_text
        self.fail_on_call = fail_on_call
        self.calls = []
        self.closed = False

    def create_chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_on_call:
            raise RuntimeError("simulated runtime inference crash")
        return {
            "choices": [{"message": {"content": self.reply_text}}],
            "usage": {"completion_tokens": 12},
        }

    def close(self):
        self.closed = True


def test_scenario1_gemma_loads_and_serves_primary(monkeypatch, isolated_model_env):
    gemma_path = _write_fake_gguf(isolated_model_env / "gemma-4-E2B-it-Q4_K_M.gguf")
    _write_fake_gguf(isolated_model_env / "coding" / "qwen2.5-coder-3b-instruct-q4_k_m.gguf")
    load_kwargs = []
    gemma_llm = _FakeLLMInstance("Paris is the capital of France.<turn|>")

    def fake_llama(**kwargs):
        load_kwargs.append(kwargs)
        return gemma_llm

    _install_fake_llama(monkeypatch, fake_llama)
    model = QwenAnswerModel(model_dir=str(isolated_model_env))
    assert model.load_model() is True

    reply = model.generate_general_response("What is the capital of France?")
    assert reply == "Paris is the capital of France."
    assert len(load_kwargs) == 1
    assert load_kwargs[0]["model_path"] == gemma_path
    assert load_kwargs[0]["chat_format"] is None
    assert gemma_llm.calls[0]["stop"] == ["<turn|>", "<eos>"]

    status = model.get_model_info()
    assert status["active_role"] == "primary"
    assert status["model_name"] == "Gemma-4-E2B-It-Q4_K_M"
    assert status["fallback_active"] is False


def test_scenario2_gemma_missing_activates_qwen_fallback(monkeypatch, isolated_model_env):
    qwen_path = _write_fake_gguf(isolated_model_env / "coding" / "qwen2.5-coder-3b-instruct-q4_k_m.gguf")
    load_kwargs = []
    qwen_llm = _FakeLLMInstance("Fallback Qwen response for France.")

    def fake_llama(**kwargs):
        load_kwargs.append(kwargs)
        return qwen_llm

    _install_fake_llama(monkeypatch, fake_llama)
    model = QwenAnswerModel(model_dir=str(isolated_model_env))
    reply = model.generate_general_response("What is the capital of France?")

    assert reply == "Fallback Qwen response for France."
    assert len(load_kwargs) == 1
    assert load_kwargs[0]["model_path"] == qwen_path
    assert load_kwargs[0]["chat_format"] == "chatml"
    assert qwen_llm.calls[0]["stop"] == ["<|im_end|>", "<|endoftext|>", "<|im_start|>"]

    status = model.get_model_info()
    assert status["active_role"] == "fallback"
    assert status["model_name"] == "Qwen2.5-Coder-3B-Instruct"
    assert status["fallback_active"] is True
    assert status["primary_status"] == "unavailable"


def test_scenario3_gemma_load_failure_activates_qwen_fallback(monkeypatch, isolated_model_env):
    gemma_path = _write_fake_gguf(isolated_model_env / "gemma-4-E2B-it-Q4_K_M.gguf", valid_header=True)
    qwen_path = _write_fake_gguf(isolated_model_env / "coding" / "qwen2.5-coder-3b-instruct-q4_k_m.gguf")
    qwen_llm = _FakeLLMInstance("Qwen loaded after Gemma init failure.")

    def fake_llama(**kwargs):
        if kwargs["model_path"] == gemma_path:
            raise ValueError("corrupted gemma tensor header")
        assert kwargs["model_path"] == qwen_path
        return qwen_llm

    _install_fake_llama(monkeypatch, fake_llama)
    model = QwenAnswerModel(model_dir=str(isolated_model_env))
    assert model.load_model() is True
    reply = model.generate_general_response("Explain local fallback.")

    assert reply == "Qwen loaded after Gemma init failure."
    status = model.get_model_info()
    assert status["active_role"] == "fallback"
    assert status["primary_status"] == "failed"
    assert status["fallback_active"] is True


def test_scenario4_gemma_inference_failure_retries_safely_on_qwen(monkeypatch, isolated_model_env):
    gemma_path = _write_fake_gguf(isolated_model_env / "gemma-4-E2B-it-Q4_K_M.gguf")
    qwen_path = _write_fake_gguf(isolated_model_env / "coding" / "qwen2.5-coder-3b-instruct-q4_k_m.gguf")
    gemma_llm = _FakeLLMInstance("", fail_on_call=True)
    qwen_llm = _FakeLLMInstance("Retried successfully with Qwen fallback.")

    def fake_llama(**kwargs):
        if kwargs["model_path"] == gemma_path:
            return gemma_llm
        assert kwargs["model_path"] == qwen_path
        return qwen_llm

    _install_fake_llama(monkeypatch, fake_llama)
    model = QwenAnswerModel(model_dir=str(isolated_model_env))
    assert model.load_model() is True
    assert model.get_model_info()["active_role"] == "primary"

    reply = model.generate_general_response("Test automatic retry on crash")
    assert reply == "Retried successfully with Qwen fallback."
    assert gemma_llm.closed is True  # Gemma unloaded before loading Qwen

    info = model.get_model_info()
    assert info["active_role"] == "fallback"
    assert info["fallback_active"] is True
    assert info["last_execution"]["retry_status"] == "succeeded"
    assert "inference_exception" in info["fallback_reason"]


def test_scenario5_gemma_recovers_after_cooldown_and_health_check(monkeypatch, isolated_model_env):
    gemma_file = isolated_model_env / "gemma-4-E2B-it-Q4_K_M.gguf"
    _write_fake_gguf(isolated_model_env / "coding" / "qwen2.5-coder-3b-instruct-q4_k_m.gguf")

    gemma_llm = _FakeLLMInstance("Restored Gemma 4 response.")
    qwen_llm = _FakeLLMInstance("Temporary Qwen response.")

    def fake_llama(**kwargs):
        if "gemma" in os.path.basename(kwargs["model_path"]).lower():
            return gemma_llm
        return qwen_llm

    _install_fake_llama(monkeypatch, fake_llama)
    model = QwenAnswerModel(model_dir=str(isolated_model_env))
    assert model.load_model() is True
    assert model.get_model_info()["active_role"] == "fallback"

    # Put valid Gemma back on disk, but stay inside cooldown -> no flip-flopping yet
    _write_fake_gguf(gemma_file)
    assert model.attempt_primary_recovery(force=False) is False
    assert model.get_model_info()["active_role"] == "fallback"
    assert model.get_model_info()["recovery_status"] == "cooldown_waiting"

    # Fast-forward past cooldown -> next request runs health check & restores Gemma
    model._fallback_activated_at = time.time() - 120.0
    model._last_recovery_attempt_at = time.time() - 120.0
    reply = model.generate_general_response("Verify recovery")
    assert reply == "Restored Gemma 4 response."
    assert qwen_llm.closed is True

    info = model.get_model_info()
    assert info["active_role"] == "primary"
    assert info["primary_status"] == "recovered"
    assert info["recovery_status"] == "recovered"
    assert info["fallback_active"] is False


def test_scenario6_both_models_fail_returns_controlled_error(monkeypatch, isolated_model_env):
    # Neither file exists -> controlled responses on all entry points
    model = QwenAnswerModel(model_dir=str(isolated_model_env))
    assert model.load_model() is False

    gen_reply = model.generate_general_response("Hello, are you working?")
    assert isinstance(gen_reply, str) and "unavailable" in gen_reply.lower()

    assert model.understand_input("Show HR leave policy") is None

    verified = CompanyAIResult(
        success=True,
        department=DepartmentEnum.GENERAL,
        intent="general_question",
        task="Test",
        summary="Verified deterministic summary.",
        findings=["Item A"],
    )
    det_answer = model.generate_answer(verified)
    assert "Verified deterministic summary." in det_answer

    # Even if both files exist and both crash at runtime -> controlled error
    _write_fake_gguf(isolated_model_env / "gemma-4-E2B-it-Q4_K_M.gguf")
    _write_fake_gguf(isolated_model_env / "coding" / "qwen2.5-coder-3b-instruct-q4_k_m.gguf")
    _install_fake_llama(monkeypatch, lambda **kwargs: _FakeLLMInstance("", fail_on_call=True))

    crash_model = QwenAnswerModel(model_dir=str(isolated_model_env))
    crash_reply = crash_model.generate_general_response("Trigger double failure")
    assert "unavailable" in crash_reply.lower()
    assert crash_model.get_model_info()["last_execution"]["retry_status"] == "failed"


def test_scenario7_concurrent_requests_single_load_thread_safe(monkeypatch, isolated_model_env):
    _write_fake_gguf(isolated_model_env / "gemma-4-E2B-it-Q4_K_M.gguf")
    _write_fake_gguf(isolated_model_env / "coding" / "qwen2.5-coder-3b-instruct-q4_k_m.gguf")
    load_count = 0
    gemma_llm = _FakeLLMInstance("Thread-safe Gemma reply.")

    def fake_llama(**kwargs):
        nonlocal load_count
        load_count += 1
        time.sleep(0.02)
        return gemma_llm

    _install_fake_llama(monkeypatch, fake_llama)
    model = QwenAnswerModel(model_dir=str(isolated_model_env))

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda i: model.generate_general_response(f"Question {i}"), range(6)))

    assert load_count == 1
    assert all(r == "Thread-safe Gemma reply." for r in results)
    assert len(gemma_llm.calls) == 6

