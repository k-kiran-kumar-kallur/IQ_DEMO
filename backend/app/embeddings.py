"""Local embeddings with fastembed (ONNX, no API key). bge-small-en-v1.5 gives 384-dimension vectors."""
import threading

from .config import DATA_DIR
from .db import get_setting

_model = None
_lock = threading.Lock()


def model():
    global _model
    with _lock:
        if _model is None:
            from fastembed import TextEmbedding
            _model = TextEmbedding(model_name=get_setting("embed_model"), cache_dir=str(DATA_DIR / "models"))
        return _model


def dimension():
    return len(embed_query("dimension probe"))


def embed_passages(texts, batch_size=64):
    return [v.tolist() for v in model().passage_embed(texts, batch_size=batch_size)]


def embed_query(text):
    return next(iter(model().query_embed(text))).tolist()
