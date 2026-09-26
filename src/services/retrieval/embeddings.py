import time
import logfire
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.config import settings

BATCH_SIZE = 50
_GEMINI_DIM = 3072
_FALLBACK_DIM = 768

_active_model : GoogleGenerativeAIEmbeddings | None = None
_model_type : str | None = None

def _probe_gemini():
    """Try one embed call to verify Gemini is reachable. Returns model or None"""
    try:
        embedding_model = GoogleGenerativeAIEmbeddings(
            model = "models/gemini-embedding-2-preview",
            google_api_key = settings.GEMINI_API_KEY
        )

        embedding_model.embed_query("probe")
        logfire.info("Gemini Embeddings ready (gemini-embedding-2-preview) (3072 dims)")
        return embedding_model
    except Exception as e : 
        logfire.warning(f"Gemini probe failed {e}. Will use Sentence-transformers fallback")
        return None


def _load_fallabck():
    from sentence_transformers import SentenceTransformer
    logfire.info("Loading sentence transformers as fallback to gemini; Model : all-mpet-base-v2")
    return SentenceTransformer("all-mpet-base-v2")


def _init():
    global _active_model , _model_type

    if _active_model is not None:
        return

    gemini_model = _probe_gemini()

    if gemini_model:
        _active_model = gemini_model,
        _model_type = "gemini"

    else:
        _active_model = _load_fallabck()
        _model_type = "fallback"

    return


def get_embedding_dim() -> int:
    """Return the embedding dimensions of the active model"""
    _init()
    return _GEMINI_DIM if _active_model == "gemini" else _FALLBACK_DIM


def _embed_batch(batch : list[str]) -> list[list[float]]:
    if _model_type == "gemini":
        for attempt in range(4):
            try:
                return _active_model.embed_documents(batch)
            except Exception as e:
                error = str(e).lower
                rate_limit = any(x in error for x in ("429" , "quota" , "rate" , "resource_exhausted"))
                if rate_limit and attempt < 3:
                    wait = 2 ** attempt
                    logfire.warning(f"Gemini Rate limit hit. Retry in {wait} seconds")
                    time.sleep(wait)
                else :
                    logfire.error(f"Gemini Embedding failed {e}")
        raise RuntimeError("Gemini rate limit hit after 4 attempts.")   
    else :
        return _active_model.encode(batch , show_progress_bar=False).toList()


#Embedding of the user query 
def embed_query(query : str) -> list[float]:
    _init()
    embedded_query : list[float] = []
    with logfire.span("Embedding the user query" , model = _model_type):
        if _model_type == "gemini":
            embedded_query = _model_type.embed_query(query)
        else :
            embedded_query = _model_type.encode(query , show_progress_bar = False).toList()
            
    return embedded_query


#Embedding of our chunks / data 
def embed_texts(texts : list[str]) -> list[list[float]]:
    _init()
    all_embeddings : list[list[float]]
    for i in range(0 , len(texts) , BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        
        with logfire.span("Embedding the batches" , model = _model_type , start = i , size = len(batch)):
            embedded_batch = _embed_batch(batch)
            all_embeddings.extend(embedded_batch)

    return all_embeddings