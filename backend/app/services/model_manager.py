"""ModelManager singleton service for loading and managing active GPT weights.
"""

import os
import torch
from loguru import logger
from typing import Dict, Any, Optional, List
from backend.app.core.config import settings
from backend.app.model.model import GPT, GPTConfig


class ModelManager:
    """Singleton service manager orchestrating the PyTorch GPT model lifecycle."""
    
    _instance: Optional['ModelManager'] = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ModelManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
            
        self.model: Optional[GPT] = None
        self.config_dict: Dict[str, Any] = {
            "learning_rate": 0.001,
            "batch_size": 4,
            "seq_len": 32,
            "num_layers": 2,
            "num_heads": 2,
            "embedding_dim": 32,
            "hidden_dim": 128,
            "epochs": 5,
            "dropout": 0.1,
        }
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._initialized = True
        logger.info(f"ModelManager singleton initialized. CPU/GPU Device: {self.device}")

    def load_model(self, force_rebuild: bool = False) -> GPT:
        """Instantiates and returns the GPT model weights.

        If model is already loaded and force_rebuild is False, returns the active instance.
        """
        if self.model is not None and not force_rebuild:
            return self.model

        logger.info("Initializing new GPT instance in ModelManager...")
        from backend.app.services.tokenizer_service import tokenizer
        vocab_size = len(tokenizer.w2i) if hasattr(tokenizer, 'w2i') and tokenizer.w2i else 80

        gpt_config = GPTConfig(
            vocab_size=vocab_size,
            context_len=int(self.config_dict["seq_len"]),
            embedding_dim=int(self.config_dict["embedding_dim"]),
            num_heads=int(self.config_dict["num_heads"]),
            hidden_dim=int(self.config_dict["hidden_dim"]),
            num_layers=int(self.config_dict["num_layers"]),
            dropout=float(self.config_dict["dropout"])
        )
        
        self.model = GPT(gpt_config)
        
        # Load last checkpoint if available to prevent starting from raw state
        checkpoint_dir = settings.CHECKPOINT_DIR
        if os.path.exists(checkpoint_dir):
            files = [f for f in os.listdir(checkpoint_dir) if f.endswith(".pt")]
            if files:
                last_ckpt = sorted(files)[-1]
                try:
                    ckpt_path = os.path.join(checkpoint_dir, last_ckpt)
                    checkpoint = torch.load(ckpt_path, map_location="cpu")
                    # Synchronize parameters
                    self.config_dict.update(checkpoint["config"])
                    self.model.load_state_dict(checkpoint["model_state_dict"])
                    logger.info(f"Automatically loaded last checkpoint in ModelManager: {last_ckpt}")
                except Exception as e:
                    logger.error(f"Failed to auto-load checkpoint on startup: {str(e)}")

        self.model = self.model.to(self.device)
        self.model.eval()
        return self.model

    def unload_model(self) -> None:
        """De-allocates model memory."""
        if self.model is not None:
            logger.info("Unloading GPT model from memory...")
            del self.model
            self.model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def reload_model(self, new_settings: Optional[Dict[str, Any]] = None) -> GPT:
        """Reloads the model structure with updated configurations."""
        logger.info("Reloading GPT model with updated settings configurations...")
        if new_settings:
            self.config_dict.update(new_settings)
        return self.load_model(force_rebuild=True)

    def get_info(self) -> Dict[str, Any]:
        """Returns details of structural parameter shapes."""
        if self.model is None:
            self.load_model()

        model_inst = self.model
        assert model_inst is not None

        layers_info = []
        for name, param in model_inst.named_parameters():
            layers_info.append({
                "layer_name": name,
                "shape": list(param.shape),
                "num_elements": param.numel(),
                "requires_grad": param.requires_grad
            })

        return {
            "model_name": "MyGPT-v2",
            "version": settings.VERSION,
            "total_params": sum(p.numel() for p in model_inst.parameters()),
            "layers_info": layers_info
        }

    def get_status(self) -> Dict[str, Any]:
        """Returns active device placement status."""
        return {
            "loaded": self.model is not None,
            "device": self.device,
            "config": self.config_dict
        }

    def load_latest_checkpoint(self) -> bool:
        """Restores tokenizer vocabulary, configuration settings, model weights, and training step states from the checkpoints directory."""
        checkpoint_dir = settings.CHECKPOINT_DIR
        if not os.path.exists(checkpoint_dir):
            return False

        latest_model = os.path.join(checkpoint_dir, "model_latest.pt")
        latest_config = os.path.join(checkpoint_dir, "config.json")
        latest_vocab = os.path.join(checkpoint_dir, "vocab.json")
        latest_state = os.path.join(checkpoint_dir, "training_state.json")

        # 1. Load Vocab
        if os.path.exists(latest_vocab):
            try:
                from backend.app.services.tokenizer_service import tokenizer
                tokenizer.load(latest_vocab)
                logger.info("Successfully restored BPETokenizer vocabulary.")
            except Exception as e:
                logger.error(f"Failed to restore vocab: {e}")

        # 2. Load Config
        if os.path.exists(latest_config):
            try:
                import json
                with open(latest_config, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.config_dict.update(cfg)
                from backend.app.services.trainer_service import trainer_service
                trainer_service.config.update(cfg)
                logger.info("Successfully restored model configuration.")
            except Exception as e:
                logger.error(f"Failed to restore config: {e}")

        # 3. Load Model weights
        if os.path.exists(latest_model):
            try:
                from backend.app.services.tokenizer_service import tokenizer
                vocab_size = len(tokenizer.w2i) if hasattr(tokenizer, 'w2i') and tokenizer.w2i else 80
                gpt_config = GPTConfig(
                    vocab_size=vocab_size,
                    context_len=int(self.config_dict["seq_len"]),
                    embedding_dim=int(self.config_dict["embedding_dim"]),
                    num_heads=int(self.config_dict["num_heads"]),
                    hidden_dim=int(self.config_dict["hidden_dim"]),
                    num_layers=int(self.config_dict["num_layers"]),
                    dropout=float(self.config_dict["dropout"])
                )
                self.model = GPT(gpt_config).to(self.device)
                self.model.load_state_dict(torch.load(latest_model, map_location=self.device))
                self.model.eval()

                from backend.app.services.trainer_service import trainer_service
                trainer_service.model = self.model
                logger.info("Successfully restored model weights.")
            except Exception as e:
                logger.error(f"Failed to restore model weights: {e}")

        # 4. Load Training history and state
        if os.path.exists(latest_state):
            try:
                import json
                with open(latest_state, "r", encoding="utf-8") as f:
                    state = json.load(f)
                from backend.app.services.trainer_service import trainer_service
                trainer_service.current_epoch = state.get("epoch", 0)
                trainer_service.current_step = state.get("step", 0)
                trainer_service.losses = state.get("losses", [])
                trainer_service.val_losses = state.get("val_losses", [])
                trainer_service.logs = state.get("logs", [])
                logger.info("Successfully restored training history.")
            except Exception as e:
                logger.error(f"Failed to restore training history: {e}")

        return True


# Global Singleton Accessor
model_manager = ModelManager()
