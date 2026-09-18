"""Qwen3-4B GGUF Model Identity Verification and Performance Benchmark.
Reads binary GGUF headers, parameter shapes, model metadata, and runs CPU inference latency tests.
"""

import os
import sys
import time
import psutil
import gguf

MODEL_PATH = r"d:\MYGPT\models\local_llm\Qwen3-4B-Q4_K_M.gguf"


def verify_gguf_metadata():
    print("=" * 60)
    print("1. GGUF METADATA & MODEL IDENTITY EXTRACTION")
    print("=" * 60)

    if not os.path.exists(MODEL_PATH):
        print(f"Error: Model file does not exist at {MODEL_PATH}")
        return False

    file_size_bytes = os.path.getsize(MODEL_PATH)
    file_size_gb = file_size_bytes / (1024 ** 3)
    print(f"Model Path:     {MODEL_PATH}")
    print(f"File Size:       {file_size_bytes:,} bytes ({file_size_gb:.2f} GB)")

    reader = gguf.GGUFReader(MODEL_PATH)
    
    print("\n--- Model Metadata Fields ---")
    fields_of_interest = [
        "general.architecture",
        "general.name",
        "general.basename",
        "general.version",
        "general.quantization_version",
        "general.file_type",
        "general.type",
        "tokenizer.ggml.model",
        "qwen2.context_length",
        "qwen2.embedding_length",
        "qwen2.block_count",
        "qwen2.feed_forward_length",
        "qwen2.attention.head_count",
        "qwen2.attention.head_count_kv",
        "qwen3.context_length",
        "qwen3.embedding_length",
        "qwen3.block_count"
    ]

    for key, field in reader.fields.items():
        val = field.contents() if hasattr(field, "contents") else field.parts
        if key in fields_of_interest or any(k in key for k in ["name", "arch", "param", "quant", "family", "author"]):
            print(f"  {key:<35}: {val}")

    # Estimate parameter count from tensors
    total_params = 0
    for tensor in reader.tensors:
        num_elements = 1
        for dim in tensor.shape:
            num_elements *= dim
        total_params += num_elements

    print(f"\nTensor Count:    {len(reader.tensors)}")
    print(f"Calculated Parameters: ~{total_params / 1e9:.2f} Billion Parameters")
    return True


def benchmark_inference():
    print("\n" + "=" * 60)
    print("2. CPU INFERENCE LATENCY & THROUGHPUT BENCHMARK")
    print("=" * 60)

    from llama_cpp import Llama

    process = psutil.Process()
    ram_before_mb = process.memory_info().rss / (1024 * 1024)

    # 1. Model Load Time
    print("Loading model into CPU memory with n_threads=4, n_ctx=2048...")
    t0 = time.time()
    llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=2048,
        n_threads=4,
        verbose=False
    )
    load_time_sec = time.time() - t0
    ram_after_mb = process.memory_info().rss / (1024 * 1024)
    ram_delta_mb = ram_after_mb - ram_before_mb

    print(f"Model Load Time:   {load_time_sec:.2f} seconds")
    print(f"Active RAM Usage:  {ram_delta_mb:.1f} MB (Total Process RAM: {ram_after_mb:.1f} MB)")

    # 2. Inference Benchmark
    system_prompt = (
        "You are the private response writer for a company AI system. "
        "Explain the verified results clearly and concisely using only supplied facts."
    )
    user_prompt = (
        "Department: TECH\n"
        "Intent: error_diagnosis\n"
        "Task: HTTP 500 Diagnosis\n"
        "Findings: Database connection pool timeout on server worker 3.\n"
        "Explain this finding to the engineer."
    )

    print("\nRunning test generation stream...")
    t_start = time.time()
    first_token_time = None
    token_count = 0
    full_text = ""

    for chunk in llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        max_tokens=150,
        temperature=0.2,
        stream=True
    ):
        if first_token_time is None:
            first_token_time = time.time() - t_start
        delta = chunk.get("choices", [{}])[0].get("delta", {})
        content = delta.get("content", "")
        if content:
            token_count += 1
            full_text += content

    total_time = time.time() - t_start
    gen_time = total_time - (first_token_time or 0)
    tokens_per_sec = (token_count / gen_time) if gen_time > 0 else 0

    print("\n--- Benchmark Results ---")
    print(f"First-Token Latency: {first_token_time * 1000:.1f} ms" if first_token_time else "N/A")
    print(f"Tokens Generated:    {token_count} tokens")
    print(f"Total Time:          {total_time:.2f} s")
    print(f"Generation Speed:    {tokens_per_sec:.2f} tokens/sec")
    print(f"CPU Threads:         4 (Intel i7-7600U)")
    print("\n--- Generated Sample ---")
    print(full_text.strip())
    print("=" * 60)


if __name__ == "__main__":
    if verify_gguf_metadata():
        benchmark_inference()
