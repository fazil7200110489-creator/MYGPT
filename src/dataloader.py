"""DataLoader module for MyGPT.

This module provides helper utilities to instantiate a PyTorch DataLoader
configured for our TextDataset.
"""

from torch.utils.data import DataLoader
from src.dataset import TextDataset


def get_dataloader(
    dataset: TextDataset,
    batch_size: int,
    shuffle: bool = True,
    drop_last: bool = False,
    num_workers: int = 0
) -> DataLoader:
    """Creates a PyTorch DataLoader configured for MyGPT TextDataset.

    Args:
        dataset: The TextDataset instance.
        batch_size: The number of sequences per batch.
        shuffle: If True, shuffles dataset samples at the start of each epoch.
        drop_last: If True, drops the last incomplete batch if the dataset size
                  is not divisible by the batch size.
        num_workers: Number of worker subprocesses to use for data loading.
                    0 means the data will be loaded in the main process.

    Returns:
        A PyTorch DataLoader instance.
    """
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        drop_last=drop_last,
        num_workers=num_workers,
        pin_memory=True if num_workers > 0 else False
    )
