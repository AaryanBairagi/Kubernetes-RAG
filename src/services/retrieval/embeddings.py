import time
import logfire
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from src.config import settings  

BATCH_SIZE = 50
GEMINI_MODEL = "models/gemini-embedding-2-preview"
FALLBACK_MODEL = "all-mpnet-base-v2"  

_active_model = None                  # GoogleGenerativeAIEmbeddings or SentenceTransformer
_model_type: str | None = None        # "gemini" or "fallback"
_embedding_dim: int | None = None     

_RATE_LIMIT_MARKERS = ("429", "quota", "rate", "resource_exhausted")
_MAX_ATTEMPTS = 4


def _probe_gemini():
    """Try one embed call to verify Gemini is reachable. Returns (model, dim) or None."""
    try:
        model = GoogleGenerativeAIEmbeddings(
            model=GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
        )
        probe_vector = model.embed_query("probe")
        dim = len(probe_vector)
        logfire.info(f"Gemini embeddings ready ({GEMINI_MODEL}, {dim} dims)")
        return model, dim
    except Exception as e:
        logfire.warning(f"Gemini probe failed: {e}. Using sentence-transformers fallback.")
        return None


def _load_fallback():
    """Load the local sentence-transformers model. Returns (model, dim)."""
    from sentence_transformers import SentenceTransformer

    logfire.info(f"Loading fallback embedding model: {FALLBACK_MODEL}")
    model = SentenceTransformer(FALLBACK_MODEL)
    return model, model.get_sentence_embedding_dimension()


def _init():
    global _active_model, _model_type, _embedding_dim

    if _active_model is not None:
        return

    probed = _probe_gemini()
    if probed:
        _active_model, _embedding_dim = probed  # FIX: no trailing comma (it made a tuple)
        _model_type = "gemini"
    else:
        _active_model, _embedding_dim = _load_fallback()
        _model_type = "fallback"


def get_embedding_dim() -> int:
    """Return the embedding dimension of the active model."""
    _init()
    return _embedding_dim  


def get_model_type() -> str:
    """Return which embedding model is active ("gemini" or "fallback")."""
    _init()
    return _model_type


def _embed_batch(batch: list[str]) -> list[list[float]]:
    if _model_type == "gemini":
        for attempt in range(_MAX_ATTEMPTS):
            try:
                return _active_model.embed_documents(batch)
            except Exception as e:
                error = str(e).lower()  # FIX: was `.lower` without ()
                is_rate_limit = any(marker in error for marker in _RATE_LIMIT_MARKERS)

                if is_rate_limit and attempt < _MAX_ATTEMPTS - 1:
                    wait = 2 ** attempt
                    logfire.warning(f"Gemini rate limit hit. Retrying in {wait}s (attempt {attempt + 1})")
                    time.sleep(wait)
                    continue

                
                logfire.error(f"Gemini embedding failed: {e}")
                raise

    return _active_model.encode(batch, show_progress_bar=False).tolist()  


def embed_query(query: str) -> list[float]:
    """Embed a single user query."""
    _init()
    with logfire.span("Embedding the user query", model=_model_type):
        if _model_type == "gemini":
            return _active_model.embed_query(query)
        return _active_model.encode(query, show_progress_bar=False).tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed document chunks in batches."""
    _init()
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        with logfire.span("Embedding batch", model=_model_type, start=i, size=len(batch)):
            all_embeddings.extend(_embed_batch(batch))

    return all_embeddings