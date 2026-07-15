# MyGPT

A GPT-style language model built completely from scratch using PyTorch.

This project is an educational, step-by-step walkthrough of building, training, and evaluating a generative transformer model from first principles.

## Project Structure

- `data/`: Raw and processed text datasets for training.
- `checkpoints/`: Model weights, optimizer states, and training checkpoints.
- `docs/`: Explanations and architectural design notes.
- `tests/`: Unit tests for every transformer component.
- `src/`: Core implementation source files:
  - `config.py`: Configuration and hyperparameters.
  - `tokenizer.py`: Character/Byte-level tokenizer.
  - `vocabulary.py`: Vocabulary mapping class.
  - `dataset.py`: PyTorch Dataset class.
  - `dataloader.py`: Custom data loading utilities.
  - `embeddings.py`: Token embeddings.
  - `positional_encoding.py`: Positional embedding layer.
  - `attention.py`: Scaled dot-product attention.
  - `multi_head_attention.py`: Multi-head attention layer.
  - `feed_forward.py`: Position-wise feed-forward network.
  - `transformer_block.py`: Single Transformer layer block.
  - `transformer.py`: Complete stack of Transformer blocks.
  - `model.py`: Model wrapper logic.
  - `optimizer.py`: custom optimizer setups.
  - `scheduler.py`: learning rate schedulers.
  - `loss.py`: loss functions.
  - `trainer.py`: training loop.
  - `inference.py`: text generation API.
  - `utils.py`: helper functions.

## Setup Instructions

1. Create a Python virtual environment:
   ```bash
   python -m venv venv
   ```
2. Activate the virtual environment:
   - Windows (PowerShell): `.\venv\Scripts\Activate.ps1`
   - Linux/macOS: `source venv/bin/activate`
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
<!-- Activate the virtual environment -->

   venv\Scripts\activate   
<!-- ### server start  -->
python -m uvicorn app.main:app --reload