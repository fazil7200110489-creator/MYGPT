"""API Router for training dataset statistics and sample preview loaders.
"""

import os
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from backend.app.core.config import settings
from backend.app.services.trainer_service import trainer_service
from backend.app.schemas.responses import DatasetRequest

router = APIRouter(tags=["Dataset"])


@router.get("/dataset")
async def get_dataset_stats() -> Dict[str, Any]:
    """Calculates corpus statistics and generates next-token prediction sample pairs."""
    from backend.app.services.tokenizer_service import tokenizer
    
    dataset_path = settings.DATASET_PATH
    if not os.path.exists(dataset_path):
        raise HTTPException(
            status_code=404, 
            detail=f"Dataset file not found at: {dataset_path}. Please verify data directory."
        )

    try:
        with open(dataset_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read dataset: {str(e)}")

    char_count = len(text)
    words_count = len(text.split())
    lines_count = len(text.splitlines())

    # Build sequence previews
    seq_len = int(trainer_service.config["seq_len"])
    ids = tokenizer.encode(text)
    total_tokens = len(ids)

    # Causal shifts pairs
    samples = []
    max_start = min(50, total_tokens - seq_len)  # Generate up to 5 previews
    for idx, i in enumerate(range(0, max_start, seq_len)):
        x_ids = ids[i : i + seq_len]
        y_ids = ids[i + 1 : i + seq_len + 1]
        
        samples.append({
            "sample_index": idx,
            "input_ids": x_ids,
            "target_ids": y_ids,
            "input_tokens": [tokenizer.i2w.get(idx, tokenizer.unk_token) for idx in x_ids],
            "target_tokens": [tokenizer.i2w.get(idx, tokenizer.unk_token) for idx in y_ids]
        })

    return {
        "dataset_name": os.path.basename(dataset_path),
        "file_size_bytes": os.path.getsize(dataset_path),
        "character_count": char_count,
        "words_count": words_count,
        "lines_count": lines_count,
        "tokens_count": total_tokens,
        "vocabulary_size": len(tokenizer.w2i),
        "seq_len": seq_len,
        "samples_preview": samples
    }


@router.post("/dataset")
async def post_dataset(req: DatasetRequest) -> Dict[str, Any]:
    """Returns causal aligned input-target sequence pairs for visual debugging."""
    from backend.app.services.tokenizer_service import tokenizer
    ids = tokenizer.encode(req.text)
    n_tokens = len(ids)
    
    if n_tokens <= req.seq_len:
        # Pad with PAD index
        pad_id = tokenizer.w2i.get(tokenizer.pad_token, 0)
        padding = [pad_id] * (req.seq_len + 1 - n_tokens)
        ids.extend(padding)
        
    samples = []
    max_start = len(ids) - req.seq_len
    for i in range(0, max_start, req.stride):
        x = ids[i : i + req.seq_len]
        y = ids[i + 1 : i + req.seq_len + 1]
        samples.append({
            "index": len(samples),
            "input_ids": x,
            "target_ids": y,
            "input_tokens": [tokenizer.i2w.get(idx, tokenizer.unk_token) for idx in x],
            "target_tokens": [tokenizer.i2w.get(idx, tokenizer.unk_token) for idx in y]
        })
        if len(samples) >= 10:  # Cap at 10 samples for view size
            break
            
    return {
        "tokens_count": n_tokens,
        "samples": samples
    }


def get_dataset_stats_internal() -> Dict[str, Any]:
    from backend.app.services.tokenizer_service import tokenizer
    from backend.app.services.trainer_service import trainer_service
    from backend.app.model.dataset import TextDataset
    import os
    
    data_dir = settings.DATA_DIR
    if not os.path.exists(data_dir):
        return {
            "total_files": 0,
            "total_words": 0,
            "total_tokens": 0,
            "dataset_size_bytes": 0,
            "estimated_steps": 0
        }
        
    txt_files = [f for f in os.listdir(data_dir) if f.endswith(".txt")]
    total_files = len(txt_files)
    
    total_size = 0
    for f in txt_files:
        total_size += os.path.getsize(os.path.join(data_dir, f))
        
    try:
        seq_len = int(trainer_service.config["seq_len"])
        dataset = TextDataset(
            text_or_path=data_dir,
            tokenizer=tokenizer,
            seq_len=seq_len,
            stride=1,
            is_path=True
        )
        total_tokens = len(dataset.tokens)
        decoded_text = tokenizer.decode(dataset.tokens.cpu().tolist())
        total_words = len(decoded_text.split())
    except Exception as e:
        print(f"Error loading combined dataset for stats: {e}")
        total_tokens = 0
        total_words = 0
        
    batch_size = int(trainer_service.config["batch_size"])
    seq_len = int(trainer_service.config["seq_len"])
    epochs = int(trainer_service.config["epochs"])
    
    num_samples = max(0, total_tokens - seq_len)
    batches_per_epoch = num_samples // batch_size if batch_size > 0 else 0
    estimated_steps = batches_per_epoch * epochs
    
    return {
        "total_files": total_files,
        "total_words": total_words,
        "total_tokens": total_tokens,
        "dataset_size_bytes": total_size,
        "estimated_steps": estimated_steps
    }


@router.get("/dataset/info")
async def get_dataset_info() -> Dict[str, Any]:
    """Returns combined dataset metrics and details."""
    return get_dataset_stats_internal()


@router.post("/dataset/reload")
async def post_dataset_reload() -> Dict[str, Any]:
    """Reloads combined dataset, re-trains BPE tokenizer, and updates model bounds."""
    from backend.app.services.tokenizer_service import tokenizer
    from backend.app.model.dataset import TextDataset
    from backend.app.services.model_manager import model_manager
    
    data_dir = settings.DATA_DIR
    try:
        dummy_ds = TextDataset(
            text_or_path=data_dir,
            tokenizer=tokenizer,
            seq_len=8,
            stride=1,
            is_path=True
        )
        combined_text = tokenizer.decode(dummy_ds.tokens.cpu().tolist())
        
        vocab_size = len(tokenizer.w2i) if tokenizer.w2i else 100
        tokenizer.train(combined_text, vocab_size=vocab_size, min_freq=1)
        
        os.makedirs(settings.CHECKPOINT_DIR, exist_ok=True)
        tokenizer.save(os.path.join(settings.CHECKPOINT_DIR, "vocab.json"))
        
        model_manager.reload_model()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload dataset: {str(e)}")
        
    return get_dataset_stats_internal()
