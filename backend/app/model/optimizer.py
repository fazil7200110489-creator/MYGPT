"""Optimizer module for MyGPT.

This module configures and instantiates optimizers (specifically AdamW) with weight
decay exclusion for normalization and bias parameters.
"""

import torch

def get_optimizer(model: torch.nn.Module, learning_rate: float, weight_decay: float = 0.01) -> torch.optim.Optimizer:
    """Configures and returns an AdamW optimizer.

    Excludes biases, normalization layer parameters, and 1D weights from weight decay
    to prevent over-regularization.
    """
    decay = []
    no_decay = []
    
    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        
        # Standard GPT normalization exclusion:
        # Any parameter with dimensions < 2 or matching bias/normalization patterns is not decayed
        if len(param.shape) >= 2 and not any(x in name.lower() for x in ["bias", "norm", "ln"]):
            decay.append(param)
        else:
            no_decay.append(param)
            
    optim_groups = [
        {"params": decay, "weight_decay": weight_decay},
        {"params": no_decay, "weight_decay": 0.0}
    ]
    
    return torch.optim.AdamW(optim_groups, lr=learning_rate)
