"""Trainer module for MyGPT.

This module coordinates model training operations in a background thread, tracking
step-by-step metrics (loss, validation losses, epochs, speed) for real-time streaming.
"""

import os
import time
import threading
from typing import Dict, Any, List, Optional
import torch
from torch.utils.data import random_split
from src.model import GPT, GPTConfig
from src.loss import GPTLoss
from src.dataloader import get_dataloader
from src.dataset import TextDataset


class TrainingManager:
    """Manages training sessions asynchronously in a background thread.

    Provides access to live progress, metrics, and logs for API and WebSockets.
    """

    def __init__(self) -> None:
        self.is_training: bool = False
        self.current_epoch: int = 0
        self.current_step: int = 0
        self.total_steps: int = 0
        self.losses: List[Dict[str, Any]] = []      # [{"step": i, "loss": f}]
        self.val_losses: List[Dict[str, Any]] = []  # [{"epoch": e, "loss": f}]
        self.logs: List[str] = []

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.model: Optional[GPT] = None
        self.tokenizer: Any = None

        # Default model and optimizer hyperparameters
        self.config: Dict[str, Any] = {
            "learning_rate": 0.001,
            "batch_size": 4,
            "seq_len": 32,
            "num_layers": 2,
            "num_heads": 2,
            "embedding_dim": 32,
            "hidden_dim": 128,
            "epochs": 10,
            "dropout": 0.1,
        }

    def add_log(self, msg: str) -> None:
        """Appends a timestamped message to the training log buffer."""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {msg}"
        self.logs.append(log_entry)
        print(log_entry)

    def configure(self, settings: Dict[str, Any], tokenizer: Any) -> None:
        """Configures BPE Tokenizer and hyperparameters prior to starting training.

        Args:
            settings: Dictionary of hyperparameter configurations.
            tokenizer: BPETokenizer instance.
        """
        self.config.update(settings)
        self.tokenizer = tokenizer
        self.add_log("Training configurations updated.")

    def start(self, dataset_path: str) -> bool:
        """Spawns the background training process.

        Args:
            dataset_path: Path to the training text file.

        Returns:
            True if training successfully started, False if already active.
        """
        if self.is_training:
            return False

        self._stop_event.clear()
        self.is_training = True
        self._thread = threading.Thread(
            target=self._run_training, args=(dataset_path,), daemon=True
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        """Requests training process termination."""
        if self.is_training:
            self._stop_event.set()
            self.add_log("Stop command received. Finalizing current step...")

    def _run_training(self, dataset_path: str) -> None:
        """Inner loop executed inside the spawned training thread."""
        try:
            self.add_log(f"Initializing training on device: {self.device}")

            # 1. Initialize Dataset & Loader
            seq_len = int(self.config["seq_len"])
            batch_size = int(self.config["batch_size"])

            self.add_log(f"Loading corpus from: {dataset_path}")
            dataset = TextDataset(
                text_or_path=dataset_path,
                tokenizer=self.tokenizer,
                seq_len=seq_len,
                stride=1,
                is_path=True,
            )

            # Split dataset into 90% train, 10% validation
            train_size = int(0.9 * len(dataset))
            val_size = len(dataset) - train_size
            if train_size <= 0 or val_size <= 0:
                train_dataset = dataset
                val_dataset = dataset
            else:
                train_dataset, val_dataset = random_split(dataset, [train_size, val_size])

            train_loader = get_dataloader(
                train_dataset, batch_size=batch_size, shuffle=True, drop_last=True
            )
            val_loader = get_dataloader(
                val_dataset, batch_size=batch_size, shuffle=False, drop_last=False
            )

            self.add_log(
                f"Dataset parsed successfully. Splits: {len(train_dataset)} train, "
                f"{len(val_dataset)} validation samples."
            )

            # 2. Build Model Stack
            gpt_config = GPTConfig(
                vocab_size=len(self.tokenizer.w2i),
                context_len=seq_len,
                embedding_dim=int(self.config["embedding_dim"]),
                num_heads=int(self.config["num_heads"]),
                hidden_dim=int(self.config["hidden_dim"]),
                num_layers=int(self.config["num_layers"]),
                dropout=float(self.config["dropout"]),
            )
            
            self.model = GPT(gpt_config).to(self.device)
            total_params = sum(p.numel() for p in self.model.parameters())
            self.add_log(f"Model initialized successfully. Total parameters: {total_params:,}")

            # 3. Setup Optimizers & Loss Function
            optimizer = torch.optim.AdamW(
                self.model.parameters(), lr=float(self.config["learning_rate"])
            )
            
            # Retrieve pad token ID to ignore in loss
            pad_id = self.tokenizer.w2i.get(self.tokenizer.pad_token, 0)
            loss_fn = GPTLoss(ignore_index=pad_id)

            epochs = int(self.config["epochs"])
            step = 0
            self.losses = []
            self.val_losses = []
            self.current_step = 0

            self.add_log("Training loop entered.")
            for epoch in range(epochs):
                if self._stop_event.is_set():
                    self.add_log("Training interrupted by user.")
                    break

                self.model.train()
                self.current_epoch = epoch + 1
                
                epoch_loss = 0.0
                num_batches = len(train_loader)

                for batch_idx, (x, y) in enumerate(train_loader):
                    if self._stop_event.is_set():
                        break

                    x, y = x.to(self.device), y.to(self.device)

                    optimizer.zero_grad()
                    logits, _ = self.model(x)
                    loss = loss_fn(logits, y)
                    loss.backward()

                    # Gradient clipping to prevent exploding gradients
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                    optimizer.step()

                    # Record statistics
                    loss_val = loss.item()
                    epoch_loss += loss_val
                    step += 1
                    self.current_step = step
                    
                    self.losses.append({"step": step, "loss": loss_val})

                    # Log progress
                    if num_batches > 5 and batch_idx % (num_batches // 5) == 0:
                        self.add_log(
                            f"Epoch {epoch + 1}/{epochs} | Batch {batch_idx + 1}/{num_batches} | "
                            f"Loss: {loss_val:.4f}"
                        )
                    elif num_batches <= 5:
                        self.add_log(
                            f"Epoch {epoch + 1}/{epochs} | Batch {batch_idx + 1}/{num_batches} | "
                            f"Loss: {loss_val:.4f}"
                        )

                    # yield thread time slice
                    time.sleep(0.01)

                # Validation metrics calculation
                if self._stop_event.is_set():
                    break

                self.model.eval()
                val_loss = 0.0
                with torch.no_grad():
                    for x_v, y_v in val_loader:
                        x_v, y_v = x_v.to(self.device), y_v.to(self.device)
                        logits_v, _ = self.model(x_v)
                        loss_v = loss_fn(logits_v, y_v)
                        val_loss += loss_v.item()

                val_loss /= max(1, len(val_loader))
                self.val_losses.append({"epoch": epoch + 1, "loss": val_loss})
                
                avg_train_loss = epoch_loss / max(1, num_batches)
                self.add_log(
                    f"Epoch {epoch + 1} Done | Train Avg Loss: {avg_train_loss:.4f} | "
                    f"Val Loss: {val_loss:.4f}"
                )

                # Save Checkpoint
                os.makedirs("checkpoints", exist_ok=True)
                checkpoint_path = f"checkpoints/checkpoint_epoch_{epoch + 1}.pt"
                torch.save(
                    {
                        "epoch": epoch + 1,
                        "model_state_dict": self.model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict(),
                        "config": self.config,
                    },
                    checkpoint_path,
                )
                self.add_log(f"Checkpoint saved: {checkpoint_path}")

            self.add_log("Training completed successfully.")

        except Exception as e:
            self.add_log(f"Fatal error during training: {str(e)}")
        finally:
            self.is_training = False
