"""Trainer module for MyGPT.

This module coordinates model training operations in a background thread, tracking
step-by-step metrics (loss, validation losses, epochs, speed) for real-time streaming.
"""

import os
import time
import threading
import torch
from typing import Dict, Any, List, Optional
from torch.utils.data import random_split
from .model import GPT, GPTConfig
from .loss import GPTLoss
from .dataloader import get_dataloader
from .dataset import TextDataset


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
        self._pause_event = threading.Event()
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

        # Dynamic metrics for WebSocket streaming
        self.current_loss: float = 0.0
        self.learning_rate: float = 0.0
        self.eta: float = 0.0
        self.current_output: str = ""
        self.current_batch: int = 0
        self.total_batches: int = 0

    def pause(self) -> None:
        """Pauses the active training loop."""
        if self.is_training and not self._pause_event.is_set():
            self._pause_event.set()
            self.add_log("Training paused.")

    def resume(self) -> None:
        """Resumes the paused training loop."""
        if self.is_training and self._pause_event.is_set():
            self._pause_event.clear()
            self.add_log("Training resumed.")

    @property
    def is_paused(self) -> bool:
        """Returns True if training is currently paused."""
        return self._pause_event.is_set()

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

            from backend.app.core.config import settings
            import json

            # Check if we should resume from the saved state
            resume = False
            latest_model_path = os.path.join(settings.CHECKPOINT_DIR, "model_latest.pt")
            latest_state_path = os.path.join(settings.CHECKPOINT_DIR, "training_state.json")
            
            if os.path.exists(latest_model_path) and os.path.exists(latest_state_path) and self.current_step > 0:
                resume = True

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
            
            if resume and self.model is not None:
                self.add_log("Resuming with current model instance in memory.")
            else:
                self.model = GPT(gpt_config).to(self.device)
                if os.path.exists(latest_model_path):
                    try:
                        self.model.load_state_dict(torch.load(latest_model_path, map_location=self.device))
                        self.add_log("Loaded latest model weights from model_latest.pt")
                    except Exception as e:
                        self.add_log(f"Warning: Failed to load model_latest.pt on start: {e}")

            # Synchronize newly initialized model weights with model_manager
            from backend.app.services.model_manager import model_manager
            model_manager.model = self.model
            model_manager.config_dict.update(self.config)

            total_params = sum(p.numel() for p in self.model.parameters())
            self.add_log(f"Model initialized successfully. Total parameters: {total_params:,}")

            # 3. Setup Optimizer, Scheduler & Loss Function
            from backend.app.model.optimizer import get_optimizer
            from backend.app.model.scheduler import get_cosine_schedule_with_warmup
            
            optimizer = get_optimizer(self.model, float(self.config["learning_rate"]))
            
            epochs = int(self.config["epochs"])
            total_steps = epochs * len(train_loader)
            self.total_steps = total_steps
            
            # Setup scheduler (warmup is 10% of total steps)
            warmup_steps = max(10, int(0.1 * total_steps))
            scheduler = get_cosine_schedule_with_warmup(optimizer, warmup_steps, total_steps)
            
            # Restore optimizer and scheduler state if resuming
            latest_opt_path = os.path.join(settings.CHECKPOINT_DIR, "optimizer.pt")
            latest_sched_path = os.path.join(settings.CHECKPOINT_DIR, "scheduler.pt")
            
            if resume:
                if os.path.exists(latest_opt_path):
                    try:
                        optimizer.load_state_dict(torch.load(latest_opt_path, map_location=self.device))
                        self.add_log("Restored optimizer state dict.")
                    except Exception as e:
                        self.add_log(f"Warning: Failed to restore optimizer state: {e}")
                if os.path.exists(latest_sched_path):
                    try:
                        scheduler.load_state_dict(torch.load(latest_sched_path, map_location=self.device))
                        self.add_log("Restored scheduler state dict.")
                    except Exception as e:
                        self.add_log(f"Warning: Failed to restore scheduler state: {e}")

            # Retrieve pad token ID to ignore in loss
            pad_id = self.tokenizer.w2i.get(self.tokenizer.pad_token, 0)
            loss_fn = GPTLoss(ignore_index=pad_id)

            if not resume:
                self.losses = []
                self.val_losses = []
                self.current_step = 0
                self.current_epoch = 0

            start_epoch = self.current_epoch
            step = self.current_step
            
            # Setup dynamic tracking states
            self.learning_rate = float(optimizer.param_groups[0]['lr'])
            self.total_batches = len(train_loader)
            self.current_batch = 0
            self.current_loss = 0.0
            self.eta = 0.0
            self.current_output = ""
            start_time = time.time()

            # Mixed precision setup
            use_amp = (self.device == "cuda")
            scaler = torch.cuda.amp.GradScaler(enabled=use_amp)

            self.add_log("Training loop entered.")
            
            for epoch in range(start_epoch, epochs):
                if self._stop_event.is_set():
                    self.add_log("Training interrupted by user.")
                    break

                self.model.train()
                self.current_epoch = epoch + 1
                
                epoch_loss = 0.0
                num_batches = len(train_loader)

                for batch_idx, (x, y) in enumerate(train_loader):
                    # Check for pause state
                    while self._pause_event.is_set() and not self._stop_event.is_set():
                        time.sleep(0.1)

                    if self._stop_event.is_set():
                        break

                    x, y = x.to(self.device), y.to(self.device)

                    optimizer.zero_grad()
                    
                    # Forward pass with mixed precision context
                    with torch.autocast(device_type="cuda" if self.device == "cuda" else "cpu", enabled=use_amp):
                        logits, _ = self.model(x)
                        loss = loss_fn(logits, y)

                    # Backward and step with scaler
                    if use_amp:
                        scaler.scale(loss).backward()
                        scaler.unscale_(optimizer)
                        torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                        scaler.step(optimizer)
                        scaler.update()
                    else:
                        loss.backward()
                        torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                        optimizer.step()

                    # Step the learning rate scheduler
                    scheduler.step()

                    # Record statistics
                    loss_val = loss.item()
                    epoch_loss += loss_val
                    step += 1
                    self.current_step = step
                    self.current_loss = loss_val
                    self.current_batch = batch_idx + 1
                    self.learning_rate = float(optimizer.param_groups[0]['lr'])
                    
                    # Calculate ETA
                    elapsed = time.time() - start_time
                    if step > 0:
                        time_per_step = elapsed / step
                        self.eta = round(time_per_step * (total_steps - step), 1)
                    else:
                        self.eta = 0.0
                    
                    self.losses.append({"step": step, "loss": loss_val})

                    # Generate dynamic text samples to show training progress
                    if step == 1 or step % 20 == 0:
                        self.model.eval()
                        with torch.no_grad():
                            try:
                                bos_id = self.tokenizer.w2i.get(self.tokenizer.bos_token, 0)
                                idx_t = torch.tensor([[bos_id]], dtype=torch.long, device=self.device)
                                from backend.app.model.inference import generate
                                out_idx = generate(self.model, idx_t, max_new_tokens=15, eos_id=-1)
                                gen_text = self.tokenizer.decode(out_idx[0].cpu().tolist())
                                self.current_output = gen_text.replace("</w>", " ")
                                self.add_log(f"Step {step} live text prediction: '{self.current_output}'")
                            except Exception as e_gen:
                                self.add_log(f"Live sample generation exception: {str(e_gen)}")
                        self.model.train()

                    # Log progress
                    if num_batches > 5 and batch_idx % (num_batches // 5) == 0:
                        self.add_log(
                            f"Epoch {epoch + 1}/{epochs} | Batch {batch_idx + 1}/{num_batches} | "
                            f"Loss: {loss_val:.4f} | LR: {self.learning_rate:.6f} | ETA: {self.eta:.1f}s"
                        )
                    elif num_batches <= 5:
                        self.add_log(
                            f"Epoch {epoch + 1}/{epochs} | Batch {batch_idx + 1}/{num_batches} | "
                            f"Loss: {loss_val:.4f} | LR: {self.learning_rate:.6f} | ETA: {self.eta:.1f}s"
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

                # Ensure checkpoint directory exists
                os.makedirs(settings.CHECKPOINT_DIR, exist_ok=True)

                # 1. Save standard per-epoch backup bundle
                checkpoint_path = os.path.join(settings.CHECKPOINT_DIR, f"checkpoint_epoch_{epoch + 1}.pt")
                torch.save(
                    {
                        "epoch": epoch + 1,
                        "model_state_dict": self.model.state_dict(),
                        "optimizer_state_dict": optimizer.state_dict(),
                        "scheduler_state_dict": scheduler.state_dict(),
                        "config": self.config,
                        "loss": avg_train_loss
                    },
                    checkpoint_path,
                )

                # 2. Save granular latest training components
                torch.save(self.model.state_dict(), os.path.join(settings.CHECKPOINT_DIR, "model_latest.pt"))
                torch.save(optimizer.state_dict(), os.path.join(settings.CHECKPOINT_DIR, "optimizer.pt"))
                torch.save(scheduler.state_dict(), os.path.join(settings.CHECKPOINT_DIR, "scheduler.pt"))
                
                # 3. Save hyperparameter config
                with open(os.path.join(settings.CHECKPOINT_DIR, "config.json"), "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=4)

                # 4. Save tokenizer vocabulary
                self.tokenizer.save(os.path.join(settings.CHECKPOINT_DIR, "vocab.json"))

                # 5. Save training stats and history state
                state_data = {
                    "epoch": epoch + 1,
                    "step": step,
                    "losses": self.losses,
                    "val_losses": self.val_losses,
                    "logs": self.logs
                }
                with open(os.path.join(settings.CHECKPOINT_DIR, "training_state.json"), "w", encoding="utf-8") as f:
                    json.dump(state_data, f, indent=4)

                self.add_log(f"Epoch {epoch + 1} Checkpoint components successfully saved.")

            self.add_log("Training completed successfully.")

        except Exception as e:
            self.add_log(f"Fatal error during training: {str(e)}")
        finally:
            self.is_training = False
