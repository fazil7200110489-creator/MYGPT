"""FastAPI server module for MyGPT Studio.

This module provides the REST APIs and WebSockets backend coordinating tokenizer analysis,
dataset inspection, embedding exploration, attention map visualization, background training,
and generative text inference.
"""

import os
import time
import torch
import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List
import asyncio

from src.model import GPT, GPTConfig
from src.loss import GPTLoss
from src.tokenizer import BPETokenizer
from src.embeddings import CustomEmbedding
from src.positional_encoding import SinusoidalPositionalEncoding
from src.attention import CausalSelfAttention
from src.trainer import TrainingManager
from src.inference import generate


app = FastAPI(title="MyGPT Studio API", version="2.0.0")

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize globally shared managers
tokenizer = BPETokenizer()
trainer = TrainingManager()

# Train tokenizer on sample corpus upon startup to ensure vocab is ready
SAMPLE_CORPUS_PATH = os.path.join("data", "sample.txt")
if os.path.exists(SAMPLE_CORPUS_PATH):
    try:
        with open(SAMPLE_CORPUS_PATH, "r", encoding="utf-8") as f:
            sample_text = f.read()
        tokenizer.train(sample_text, vocab_size=100, min_freq=1)
        trainer.configure({}, tokenizer)
        print(f"Pre-initialized BPETokenizer with {len(tokenizer.w2i)} tokens.")
    except Exception as e:
        print(f"Failed to pre-train BPE: {str(e)}")
else:
    # Minimal initial training on a dummy string to avoid empty vocabs
    tokenizer.train("the cat sat on the mat. learning is rewarding.", vocab_size=50, min_freq=1)
    trainer.configure({}, tokenizer)


# Pydantic Schemas for Requests
class TextRequest(BaseModel):
    text: str


class DatasetRequest(BaseModel):
    text: str
    seq_len: int
    stride: int = 1


class TrainConfigureRequest(BaseModel):
    settings: Dict[str, Any]


class InferenceRequest(BaseModel):
    prompt: str
    max_tokens: int = 50
    temperature: float = 1.0
    top_k: int = 0
    top_p: float = 0.0


class LoadCheckpointRequest(BaseModel):
    filename: str


# REST Endpoints

@app.get("/api/dashboard")
async def get_dashboard() -> Dict[str, Any]:
    """Retrieves high-level dashboard configuration and status metrics."""
    return {
        "model_name": "MyGPT-v2",
        "device": trainer.device,
        "is_training": trainer.is_training,
        "vocab_size": len(tokenizer.w2i),
        "embedding_dim": trainer.config["embedding_dim"],
        "num_layers": trainer.config["num_layers"],
        "num_heads": trainer.config["num_heads"],
        "context_len": trainer.config["seq_len"],
        "current_epoch": trainer.current_epoch,
        "current_step": trainer.current_step,
        "total_params": sum(p.numel() for p in trainer.model.parameters()) if trainer.model else 0,
    }


@app.post("/api/tokenize")
async def post_tokenize(req: TextRequest) -> Dict[str, Any]:
    """Tokenizes text and returns subword strings and vocab IDs."""
    subwords = tokenizer.tokenize(req.text)
    ids = tokenizer.encode(req.text)
    mapping = [{"token": tok, "id": idx} for tok, idx in zip(subwords, ids)]
    return {
        "text": req.text,
        "tokens": subwords,
        "ids": ids,
        "mapping": mapping
    }


@app.get("/api/vocabulary")
async def get_vocabulary() -> Dict[str, Any]:
    """Returns the list of all token mapping keys and values."""
    # Return sorted vocabulary items
    items = sorted(tokenizer.w2i.items(), key=lambda x: x[1])
    return {
        "vocabulary": [{"id": idx, "token": tok} for tok, idx in items]
    }


@app.post("/api/dataset")
async def post_dataset(req: DatasetRequest) -> Dict[str, Any]:
    """Returns causal aligned input-target sequence pairs for visual debugging."""
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


@app.post("/api/embedding")
async def post_embedding(req: TextRequest) -> Dict[str, Any]:
    """Returns token ID coordinates from the embedding matrix for text visualization."""
    ids = tokenizer.encode(req.text)
    if not ids:
        return {"ids": [], "embeddings": []}

    # Simulate embeddings lookup using a temp layer or model layer if initialized
    embedding_dim = int(trainer.config["embedding_dim"])
    embed_layer = None
    if trainer.model:
        embed_layer = trainer.model.token_embeddings
    else:
        embed_layer = CustomEmbedding(len(tokenizer.w2i), embedding_dim)

    # Perform lookup
    token_tensor = torch.tensor([ids], dtype=torch.long)
    with torch.no_grad():
        vectors = embed_layer(token_tensor).squeeze(0).cpu().numpy()

    # Convert vectors to serializable format
    embeddings_data = []
    for idx, vec in zip(ids, vectors):
        embeddings_data.append({
            "id": idx,
            "token": tokenizer.i2w.get(idx, tokenizer.unk_token),
            "vector": vec.tolist(),
            "mean": float(vec.mean()),
            "std": float(vec.std()),
            "min": float(vec.min()),
            "max": float(vec.max()),
        })

    return {
        "shape": [len(ids), embedding_dim],
        "embeddings": embeddings_data
    }


@app.post("/api/attention")
async def post_attention(req: TextRequest) -> Dict[str, Any]:
    """Runs a forward pass and returns attention score matrices for the visualizer."""
    ids = tokenizer.encode(req.text)
    if not ids:
        return {"tokens": [], "attention_weights": []}

    seq_len = len(ids)
    embedding_dim = int(trainer.config["embedding_dim"])
    num_heads = int(trainer.config["num_heads"])

    # If model is not loaded, initialize a temp model to generate values
    model_inst = trainer.model
    if not model_inst:
        cfg = GPTConfig(
            vocab_size=len(tokenizer.w2i),
            context_len=max(128, seq_len),
            embedding_dim=embedding_dim,
            num_heads=num_heads,
            num_layers=1
        )
        model_inst = GPT(cfg)

    model_inst.eval()
    
    # Forward pass to pluck attention weights
    input_tensor = torch.tensor([ids], dtype=torch.long)
    try:
        with torch.no_grad():
            _, attentions = model_inst(input_tensor)
        
        # attentions is list of layers: each shape (1, num_heads, seq_len, seq_len)
        # Select the first layer's weights
        layer_weights = attentions[0][0].cpu().numpy().tolist()  # (num_heads, seq_len, seq_len)
    except Exception as e:
        # Fallback if seq_len is incompatible with model configuration context limits
        layer_weights = [[[1.0 if j <= i else 0.0 for j in range(seq_len)] for i in range(seq_len)] for _ in range(num_heads)]
        print(f"Attention execution fallback triggered: {str(e)}")

    tokens = [tokenizer.i2w.get(idx, tokenizer.unk_token) for idx in ids]
    return {
        "tokens": tokens,
        "attention_weights": layer_weights  # List of lists of lists: (num_heads, seq_len, seq_len)
    }


@app.post("/api/train/start")
async def post_train_start(req: TrainConfigureRequest) -> Dict[str, Any]:
    """Triggers background training thread."""
    if trainer.is_training:
        return {"success": False, "message": "Training is already in progress."}

    trainer.configure(req.settings, tokenizer)
    success = trainer.start(SAMPLE_CORPUS_PATH)
    if success:
        return {"success": True, "message": "Training successfully started."}
    return {"success": False, "message": "Could not launch training."}


@app.post("/api/train/stop")
async def post_train_stop() -> Dict[str, Any]:
    """Halts active training threads."""
    if not trainer.is_training:
        return {"success": False, "message": "Training is not active."}
    trainer.stop()
    return {"success": True, "message": "Stop command sent to trainer."}


@app.get("/api/train/status")
async def get_train_status() -> Dict[str, Any]:
    """Returns active training metric parameters."""
    return {
        "is_training": trainer.is_training,
        "current_epoch": trainer.current_epoch,
        "current_step": trainer.current_step,
        "losses": trainer.losses[-100:],  # Return last 100 steps
        "val_losses": trainer.val_losses,
        "logs": trainer.logs[-50:]  # Last 50 log lines
    }


@app.post("/api/inference")
async def post_inference(req: InferenceRequest) -> Dict[str, Any]:
    """Generates autoregressive token sequences using selected parameters."""
    ids = tokenizer.encode(req.prompt)
    if not ids:
        ids = [tokenizer.w2i[tokenizer.bos_token]]

    input_tensor = torch.tensor([ids], dtype=torch.long).to(trainer.device)

    # Use model from trainer if available, otherwise mock-load a temp model
    model_inst = trainer.model
    if not model_inst:
        # Check if a checkpoint exists and load it automatically
        checkpoint_dir = "checkpoints"
        if os.path.exists(checkpoint_dir):
            files = [f for f in os.listdir(checkpoint_dir) if f.endswith(".pt")]
            if files:
                last_ckpt = sorted(files)[-1]
                try:
                    ckpt = torch.load(os.path.join(checkpoint_dir, last_ckpt), map_location="cpu")
                    cfg_dict = ckpt["config"]
                    cfg = GPTConfig(
                        vocab_size=len(tokenizer.w2i),
                        context_len=int(cfg_dict["seq_len"]),
                        embedding_dim=int(cfg_dict["embedding_dim"]),
                        num_heads=int(cfg_dict["num_heads"]),
                        hidden_dim=int(cfg_dict["hidden_dim"]),
                        num_layers=int(cfg_dict["num_layers"])
                    )
                    model_inst = GPT(cfg)
                    model_inst.load_state_dict(ckpt["model_state_dict"])
                    model_inst = model_inst.to(trainer.device)
                    print(f"Inference: Loaded active checkpoint {last_ckpt}")
                except Exception as e:
                    print(f"Failed to auto-load checkpoint: {str(e)}")

    if not model_inst:
        cfg = GPTConfig(
            vocab_size=len(tokenizer.w2i),
            context_len=int(trainer.config["seq_len"]),
            embedding_dim=int(trainer.config["embedding_dim"]),
            num_heads=int(trainer.config["num_heads"]),
            hidden_dim=int(trainer.config["hidden_dim"]),
            num_layers=int(trainer.config["num_layers"])
        )
        model_inst = GPT(cfg).to(trainer.device)

    # Perform generation
    eos_id = tokenizer.w2i.get(tokenizer.eos_token, -1)
    with torch.no_grad():
        output_ids = generate(
            model=model_inst,
            idx=input_tensor,
            max_new_tokens=req.max_tokens,
            temperature=req.temperature,
            top_k=req.top_k,
            top_p=req.top_p,
            eos_id=eos_id
        )

    output_list = output_ids[0].cpu().tolist()
    generated_text = tokenizer.decode(output_list)
    
    # Format generated output
    return {
        "prompt": req.prompt,
        "input_ids": ids,
        "output_ids": output_list,
        "generated_text": generated_text
    }


@app.get("/api/checkpoints")
async def get_checkpoints() -> Dict[str, Any]:
    """Lists saved checkpoint metadata from directories."""
    checkpoints_list = []
    checkpoint_dir = "checkpoints"
    if os.path.exists(checkpoint_dir):
        files = [f for f in os.listdir(checkpoint_dir) if f.endswith(".pt")]
        for f in sorted(files):
            filepath = os.path.join(checkpoint_dir, f)
            stats = os.stat(filepath)
            
            # Read metadata
            try:
                ckpt = torch.load(filepath, map_location="cpu")
                epoch = ckpt.get("epoch", "-")
                loss = ckpt.get("loss", "N/A")
                if isinstance(loss, float):
                    loss = f"{loss:.4f}"
            except Exception:
                epoch = "-"
                loss = "N/A"

            checkpoints_list.append({
                "filename": f,
                "epoch": epoch,
                "loss": loss,
                "size_mb": round(stats.st_size / (1024 * 1024), 2),
                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stats.st_mtime))
            })
    return {"checkpoints": checkpoints_list}


@app.post("/api/checkpoint/load")
async def post_checkpoint_load(req: LoadCheckpointRequest) -> Dict[str, Any]:
    """Loads weights from a saved checkpoint into the active model state."""
    filepath = os.path.join("checkpoints", req.filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Checkpoint file not found.")

    try:
        ckpt = torch.load(filepath, map_location="cpu")
        cfg_dict = ckpt["config"]
        
        # Build model structure matching configurations
        cfg = GPTConfig(
            vocab_size=len(tokenizer.w2i),
            context_len=int(cfg_dict["seq_len"]),
            embedding_dim=int(cfg_dict["embedding_dim"]),
            num_heads=int(cfg_dict["num_heads"]),
            hidden_dim=int(cfg_dict["hidden_dim"]),
            num_layers=int(cfg_dict["num_layers"])
        )
        
        trainer.model = GPT(cfg)
        trainer.model.load_state_dict(ckpt["model_state_dict"])
        trainer.model = trainer.model.to(trainer.device)
        
        # Sync configurations
        trainer.config.update(cfg_dict)
        trainer.current_epoch = ckpt.get("epoch", 1)
        
        trainer.add_log(f"Successfully loaded checkpoint: {req.filename}")
        return {"success": True, "message": f"Loaded checkpoint: {req.filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load checkpoint: {str(e)}")


@app.get("/api/settings")
async def get_settings() -> Dict[str, Any]:
    """Returns active settings parameters."""
    return {"settings": trainer.config}


@app.post("/api/settings/save")
async def post_settings_save(req: TrainConfigureRequest) -> Dict[str, Any]:
    """Updates hyperparameter settings."""
    trainer.configure(req.settings, tokenizer)
    return {"success": True, "message": "Settings saved successfully."}


# WebSockets Live Streaming Endpoint

@app.websocket("/ws/training")
async def websocket_training(websocket: WebSocket) -> None:
    """Streams real-time metrics, losses, and logs to connected frontend subscribers."""
    await websocket.accept()
    last_step = 0
    try:
        while True:
            # Yield info if active, else rest
            status_data = {
                "is_training": trainer.is_training,
                "current_epoch": trainer.current_epoch,
                "current_step": trainer.current_step,
                # Stream logs and step losses added since last interval
                "new_losses": trainer.losses[last_step:],
                "val_losses": trainer.val_losses,
                "logs": trainer.logs[-20:]  # Send trailing logs
            }
            last_step = len(trainer.losses)
            
            await websocket.send_json(status_data)
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        print("WebSocket client disconnected from training stream.")
    except Exception as e:
        print(f"WebSocket training error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
