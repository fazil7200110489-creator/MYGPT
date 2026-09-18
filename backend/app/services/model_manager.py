"""ModelManager singleton service for loading and managing active GPT weights.
"""

import os
import json
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
        self._total_params: Optional[int] = None
        self.config_dict: Dict[str, Any] = {
            "learning_rate": 0.001,
            "batch_size": 4,
            "seq_len": 256,
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

    def get_total_params(self) -> int:
        """Returns cached total parameters count without expensive iteration."""
        if self._total_params is not None:
            return self._total_params
        if self.model is not None:
            self._total_params = sum(p.numel() for p in self.model.parameters())
            return self._total_params
        return 0


        # Check if saved config exists to sync initial defaults
        checkpoint_dir = settings.CHECKPOINT_DIR
        config_path = os.path.join(checkpoint_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    saved_cfg = json.load(f)
                self.config_dict.update(saved_cfg)
            except Exception as e:
                logger.warning(f"Could not read config.json on init: {e}")

    def load_persistent_config(self) -> Dict[str, int]:
        """Loads max_sequence_length and embedding_dimension from persistent config file."""
        config_path = os.path.join(settings.CHECKPOINT_DIR, "model_config.json")
        defaults = {
            "max_sequence_length": 16,
            "embedding_dimension": 16
        }
        if not os.path.exists(config_path):
            return defaults
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "max_sequence_length": data.get("max_sequence_length", 16),
                "embedding_dimension": data.get("embedding_dimension", 16)
            }
        except Exception as e:
            logger.error(f"Failed to load persistent config: {e}")
            return defaults

    def save_persistent_config(self, max_sequence_length: int, embedding_dimension: int) -> None:
        """Saves max_sequence_length and embedding_dimension to persistent config file."""
        os.makedirs(settings.CHECKPOINT_DIR, exist_ok=True)
        config_path = os.path.join(settings.CHECKPOINT_DIR, "model_config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({
                    "max_sequence_length": max_sequence_length,
                    "embedding_dimension": embedding_dimension
                }, f, indent=2)
            logger.info(f"Saved persistent config: seq_len={max_sequence_length}, embedding_dim={embedding_dimension}")
        except Exception as e:
            logger.error(f"Failed to save persistent config: {e}")

    def load_model(self, force_rebuild: bool = False) -> GPT:
        """Instantiates and returns the GPT model weights.

        If model is already loaded and force_rebuild is False, returns the active instance.
        Authoritatively uses authentic checkpoint configuration as source of truth.
        """
        if self.model is not None and not force_rebuild:
            return self.model

        checkpoint_dir = settings.CHECKPOINT_DIR
        latest_model = os.path.join(checkpoint_dir, "model_latest.pt")
        latest_config = os.path.join(checkpoint_dir, "config.json")

        # 1. Primary path: Load production model_latest.pt if available
        if os.path.exists(latest_model) and os.path.exists(latest_config):
            success = self.load_latest_checkpoint()
            if success and self.model is not None:
                return self.model

        # 2. Secondary / legacy path: Load from epoch checkpoint if model_latest is not present
        if os.path.exists(checkpoint_dir):
            import re
            files = [f for f in os.listdir(checkpoint_dir) if f.startswith("checkpoint_epoch_") and f.endswith(".pt")]
            if files:
                try:
                    last_ckpt = sorted(files, key=lambda x: int(re.findall(r'\d+', x)[0]))[-1]
                    ckpt_path = os.path.join(checkpoint_dir, last_ckpt)
                    checkpoint = torch.load(ckpt_path, map_location="cpu")
                    ckpt_config = checkpoint.get("config", {})
                    state_dict = checkpoint.get("model_state_dict", {})
                    
                    # Deduce vocab size from checkpoint tensor weights
                    ckpt_vocab_size = state_dict.get("token_embeddings.weight", None)
                    vocab_size = ckpt_vocab_size.shape[0] if ckpt_vocab_size is not None else 100
                    
                    gpt_config = GPTConfig(
                        vocab_size=vocab_size,
                        context_len=int(ckpt_config.get("seq_len", 32)),
                        embedding_dim=int(ckpt_config.get("embedding_dim", 32)),
                        num_heads=int(ckpt_config.get("num_heads", 2)),
                        hidden_dim=int(ckpt_config.get("hidden_dim", 128)),
                        num_layers=int(ckpt_config.get("num_layers", 2)),
                        dropout=float(ckpt_config.get("dropout", 0.1))
                    )
                    
                    self.config_dict.update(ckpt_config)
                    self.model = GPT(gpt_config)
                    self.model.load_state_dict(state_dict, strict=True)
                    self.model = self.model.to(self.device)
                    self.model.eval()
                    logger.info(
                        f"Loaded legacy checkpoint: {last_ckpt} | "
                        f"vocab={vocab_size}, dim={gpt_config.embedding_dim}, seq={gpt_config.context_len}"
                    )
                    return self.model
                except Exception as e:
                    logger.error(f"Failed to load epoch checkpoint: {str(e)}")

        # 3. Fallback path: Instantiate raw model from current config_dict
        logger.info("Initializing baseline GPT instance in ModelManager...")
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
        """Restores tokenizer vocabulary, configuration settings, model weights, and training step states from the checkpoints directory.
        
        The authentic checkpoint file and saved config.json serve as authoritative source of truth.
        """
        checkpoint_dir = settings.CHECKPOINT_DIR
        if not os.path.exists(checkpoint_dir):
            logger.warning(f"Checkpoint directory does not exist: {checkpoint_dir}")
            return False

        latest_model = os.path.join(checkpoint_dir, "model_latest.pt")
        latest_config = os.path.join(checkpoint_dir, "config.json")
        latest_vocab = os.path.join(checkpoint_dir, "vocab.json")
        latest_state = os.path.join(checkpoint_dir, "training_state.json")

        if not os.path.exists(latest_model):
            logger.warning(f"model_latest.pt not found at: {latest_model}")
            return False

        # 1. Restore Tokenizer Vocabulary
        if os.path.exists(latest_vocab):
            try:
                from backend.app.services.tokenizer_service import tokenizer
                tokenizer.load(latest_vocab)
                logger.info(f"Successfully restored BPETokenizer vocabulary ({len(tokenizer.w2i)} tokens).")
            except Exception as e:
                logger.error(f"Failed to restore vocab from {latest_vocab}: {e}")
                return False
        else:
            logger.warning(f"vocab.json not found at {latest_vocab}")

        from backend.app.services.tokenizer_service import tokenizer
        vocab_size = len(tokenizer.w2i) if hasattr(tokenizer, 'w2i') and tokenizer.w2i else 1113

        # 2. Restore Model Configuration from config.json (Authoritative)
        if os.path.exists(latest_config):
            try:
                with open(latest_config, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.config_dict.update(cfg)
                from backend.app.services.trainer_service import trainer_service
                trainer_service.config.update(cfg)
            except Exception as e:
                logger.error(f"Failed to restore config from {latest_config}: {e}")
                return False

        # Read authentic parameters from config_dict
        context_len = int(self.config_dict.get("seq_len", 256))
        embedding_dim = int(self.config_dict.get("embedding_dim", 32))
        num_heads = int(self.config_dict.get("num_heads", 2))
        hidden_dim = int(self.config_dict.get("hidden_dim", 128))
        num_layers = int(self.config_dict.get("num_layers", 2))
        dropout = float(self.config_dict.get("dropout", 0.1))

        # 3. Construct GPT model with authentic checkpoint configuration
        gpt_config = GPTConfig(
            vocab_size=vocab_size,
            context_len=context_len,
            embedding_dim=embedding_dim,
            num_heads=num_heads,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            dropout=dropout
        )

        try:
            state_dict = torch.load(latest_model, map_location=self.device)
            
            # Verify vocab size compatibility before loading
            ckpt_vocab_size = state_dict.get("token_embeddings.weight", None)
            if ckpt_vocab_size is not None and ckpt_vocab_size.shape[0] != vocab_size:
                logger.error(
                    f"Tokenizer vocab size ({vocab_size}) does not match checkpoint vocab size ({ckpt_vocab_size.shape[0]})."
                )
                return False

            new_model = GPT(gpt_config).to(self.device)
            new_model.load_state_dict(state_dict, strict=True)
            new_model.eval()
            self.model = new_model

            from backend.app.services.trainer_service import trainer_service
            trainer_service.model = self.model

            logger.info(
                f"Loaded checkpoint: model_latest.pt\n"
                f"Model configuration: vocab={vocab_size}, embedding_dim={embedding_dim}, "
                f"layers={num_layers}, heads={num_heads}, context={context_len}, hidden_dim={hidden_dim}\n"
                f"Model weights restored successfully (0 tensor shape mismatches)."
            )
        except Exception as e:
            logger.error(f"Failed to restore model weights from {latest_model}: {e}")
            return False

        # 4. Load Training history and state
        if os.path.exists(latest_state):
            try:
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
