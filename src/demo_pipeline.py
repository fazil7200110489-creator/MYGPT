"""Demonstration script for the MyGPT Dataset and DataLoader pipeline.
"""

import os
from src.vocabulary import Vocabulary
from src.tokenizer import WordTokenizer
from src.dataset import TextDataset
from src.dataloader import get_dataloader


def main() -> None:
    print("--- MyGPT Dataset & DataLoader Pipeline Demo ---")

    # Path to sample corpus
    data_path = os.path.join("data", "sample.txt")

    # 1. Initialize Vocabulary and Tokenizer
    print("\n1. Initializing Vocabulary & Tokenizer...")
    vocab = Vocabulary()
    
    # Initialize a temporary tokenizer to build the vocabulary
    temp_tokenizer = WordTokenizer(vocab)
    vocab.build_from_file(data_path, tokenize_fn=temp_tokenizer.tokenize, min_freq=1)
    
    print(f"Vocabulary size: {len(vocab)} words.")
    print("Special tokens registered:")
    print(f"  PAD: {vocab.pad_token} (ID: {vocab.pad_id})")
    print(f"  UNK: {vocab.unk_token} (ID: {vocab.unk_id})")
    print(f"  BOS: {vocab.bos_token} (ID: {vocab.bos_id})")
    print(f"  EOS: {vocab.eos_token} (ID: {vocab.eos_id})")

    # Initialize final tokenizer linked to the generated vocab
    tokenizer = WordTokenizer(vocab)

    # 2. Initialize TextDataset
    seq_len = 6
    stride = 1
    print(f"\n2. Creating TextDataset (seq_len={seq_len}, stride={stride})...")
    dataset = TextDataset(data_path, tokenizer, seq_len=seq_len, stride=stride, is_path=True)
    print(f"Total training sequences (samples): {len(dataset)}")

    # 3. Create DataLoader
    batch_size = 2
    print(f"\n3. Creating DataLoader (batch_size={batch_size}, shuffle=False)...")
    dataloader = get_dataloader(dataset, batch_size=batch_size, shuffle=False, drop_last=True)

    # 4. Display first 5 batches
    print("\n4. Displaying the first 5 batches:\n" + "=" * 70)
    for batch_idx, (batch_x, batch_y) in enumerate(dataloader):
        if batch_idx >= 5:
            break
        print(f"\nBatch {batch_idx + 1}:")
        print(f"  Input Tensor Shape : {list(batch_x.shape)}")
        print(f"  Target Tensor Shape: {list(batch_y.shape)}")
        print("  " + "-" * 60)
        
        for sample_idx in range(batch_size):
            x_ids = batch_x[sample_idx].tolist()
            y_ids = batch_y[sample_idx].tolist()
            
            x_text = tokenizer.decode(x_ids)
            y_text = tokenizer.decode(y_ids)
            
            print(f"  Sample {sample_idx + 1}:")
            print(f"    Input (X) IDs  : {x_ids}")
            print(f"    Input (X) Text : '{x_text}'")
            print(f"    Target (Y) IDs : {y_ids}")
            print(f"    Target (Y) Text: '{y_text}'")
            print("  " + "-" * 60)
            
    print("=" * 70)
    print("\nCausal Shift Explanation:")
    print("Notice that for every sample:")
    print("  - The 'Target (Y)' sequence is identical to the 'Input (X)' sequence, shifted left by exactly 1 token.")
    print("  - For example, if X is: [the, cat, sat, on, the, mat]")
    print("                 Y is: [cat, sat, on, the, mat, .]")
    print("  - At input position 0 ('the'), the model must predict the target 'cat'.")
    print("  - At input position 1 ('the cat'), it must predict 'sat', and so forth.")


if __name__ == "__main__":
    main()
