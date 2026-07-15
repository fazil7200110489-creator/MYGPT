"""API Router for tokenization, encoding, decoding, and vocabulary explorers.
"""

from fastapi import APIRouter
from typing import Dict, Any, List
from pydantic import BaseModel
from backend.app.schemas.responses import TokenizerRequest, TokenizerResponse

router = APIRouter(tags=["Tokenizer"])


# Custom schemas for pure lists or text requests
class EncodeRequest(BaseModel):
    text: str
    add_bos: bool = False
    add_eos: bool = False


class DecodeRequest(BaseModel):
    ids: List[int]
    skip_special: bool = True


@router.post("/tokenize", response_model=TokenizerResponse)
async def tokenize_text(req: TokenizerRequest) -> Dict[str, Any]:
    """Tokenizes text and returns subword tokens, IDs, and mapping entries."""
    from backend.app.services.tokenizer_service import tokenizer
    subwords = tokenizer.tokenize(req.text)
    ids = tokenizer.encode(req.text)
    mapping = [{"token": tok, "id": idx} for tok, idx in zip(subwords, ids)]
    return {
        "text": req.text,
        "tokens": subwords,
        "ids": ids,
        "mapping": mapping
    }


@router.post("/encode")
async def encode_text(req: EncodeRequest) -> Dict[str, Any]:
    """Converts a raw string into a list of token ID integers."""
    from backend.app.services.tokenizer_service import tokenizer
    ids = tokenizer.encode(req.text, add_bos=req.add_bos, add_eos=req.add_eos)
    return {"ids": ids}


@router.post("/decode")
async def decode_ids(req: DecodeRequest) -> Dict[str, Any]:
    """Reconstructs text from a list of token ID integers."""
    from backend.app.services.tokenizer_service import tokenizer
    text = tokenizer.decode(req.ids, skip_special=req.skip_special)
    return {"text": text}


@router.get("/vocabulary")
async def get_vocabulary() -> Dict[str, Any]:
    """Returns the list of all token mapping keys and values sorted by ID."""
    from backend.app.services.tokenizer_service import tokenizer
    items = sorted(tokenizer.w2i.items(), key=lambda x: x[1])
    return {
        "vocabulary": [{"id": idx, "token": tok} for tok, idx in items]
    }
