import os
import json
import uuid
import logfire

from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.config import settings
from src.ingestion.chunking.splitter import chunk_text
from src.ingestion.loaders.office import parse_office
from src.ingestion.loaders.pdf import parse_pdf
from src.ingestion.loaders.text import parse_text
from src.ingestion.loaders.html import html_parser
from src.services.retrieval.embeddings import embed_texts, get_embedding_dim, get_model_type

logfire.configure(service_name="enterprise-rag-app", send_to_logfire="if-token-present")

settings.validate()

qd_client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
)

PROCESSED_DATA_DIR = "processed_data"
UPSERT_BATCH_SIZE = 100


def save_processed_metadata_locally(data: dict, filename: str, source_type: str) -> str:
    """Save parsed chunk metadata as JSON in processed_data/<source_type>/."""
    folder = os.path.join(PROCESSED_DATA_DIR, source_type)
    os.makedirs(folder, exist_ok=True)  
    dest = os.path.join(folder, f"{filename}.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return dest


def process_file(file_path: str, filename: str, source_type: str):
    """Parse -> Chunk -> Save Locally -> Embed -> Save to Qdrant Cloud"""
    with logfire.span("Processing file", file=filename, source=source_type):
        try:
            # 1. Extract text based on the file extension
            file_extension = filename.lower().rsplit(".", 1)[-1] 

            if file_extension == "pdf":
                full_text = parse_pdf(file_path=file_path)
            elif file_extension in ("html", "htm"):
                full_text = html_parser(file_path=file_path)
            elif file_extension in ("docx", "pptx"):
                full_text = parse_office(file_path=file_path)
            elif file_extension == "txt":
                full_text = parse_text(file_path=file_path)
            else:
                logfire.warning(f"Skipping unsupported file type: {filename}")
                return

            if not full_text or not full_text.strip():
                logfire.warning(f"No text extracted from {filename}. Skipping.")
                return

            # 2. Chunk the extracted text
            chunks = chunk_text(full_text)
            if not chunks:
                logfire.warning(f"No chunks formed for {filename}. Skipping.")
                return

            # 3. Save chunks locally
            processed_metadata = {
                "filename": filename,
                "source_type": source_type,
                "chunks": chunks,
            }
            local_path = save_processed_metadata_locally(
                data=processed_metadata, filename=filename, source_type=source_type
            )
            logfire.info(f"Saved processed data locally at: {local_path}")

            # 4. Embed and upsert to Qdrant
            with logfire.span("Vectorizing and embedding", chunks=len(chunks)):
                embeddings = embed_texts(chunks)
                if len(embeddings) != len(chunks):
                    raise RuntimeError(
                        f"Got {len(embeddings)} embeddings for {len(chunks)} chunks in {filename}"
                    )

                model_type = get_model_type()
                points = []
                for i, (chunk, vector_emb) in enumerate(zip(chunks, embeddings)): 
                    # Deterministic ID: re-ingesting the same file overwrites its chunks
                    # instead of creating duplicates.
                    point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_type}/{filename}/{i}"))
                    points.append(
                        # Qdrant stores data as "points": id + vector + payload (metadata)
                        models.PointStruct(
                            id=point_id,
                            vector=vector_emb,
                            payload={
                                "text": chunk,
                                "source": filename,
                                "source_type": source_type,
                                "chunk_index": i,
                                "embedding_model": model_type,
                            },
                        )
                    )

                # Upsert in batches so large files don't exceed request-size limits
                for start in range(0, len(points), UPSERT_BATCH_SIZE):
                    qd_client.upsert(
                        collection_name=settings.QDRANT_COLLECTION,
                        points=points[start : start + UPSERT_BATCH_SIZE],
                    )

                logfire.info(f"Indexed {len(points)} points to Qdrant from {filename}")

        except Exception as e:
            logfire.error(f"Error while processing {filename}: {e}")


def process_directory(dir_path: str, source_type: str):
    """Process every file in the directory (top level only)."""
    with logfire.span("Scanning directory", dir=dir_path, source=source_type):
        if not os.path.isdir(dir_path):
            logfire.warning(f"Directory not found: {dir_path}")
            return

        files = sorted(
            f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))
        )
        logfire.info(f"Found {len(files)} files in {dir_path}. Processing each file...")

        for filename in files:
            process_file(
                file_path=os.path.join(dir_path, filename),
                filename=filename,
                source_type=source_type,
            )


def ensure_collection(wipe: bool = False):
    """Create the Qdrant collection if needed; optionally drop it first."""
    name = settings.QDRANT_COLLECTION

    if wipe and qd_client.collection_exists(name):  
        qd_client.delete_collection(name)
        logfire.warning(f"Wiped Qdrant collection: {name}")

    dim = get_embedding_dim()

    if not qd_client.collection_exists(name):
        qd_client.create_collection(  
            collection_name=name,
            vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
        )
        logfire.info(f"Created Qdrant collection '{name}' with dim {dim}")
        return

    # Collection already exists: make sure its vector size matches the active model
    vectors = qd_client.get_collection(name).config.params.vectors
    if isinstance(vectors, models.VectorParams) and vectors.size != dim:
        raise RuntimeError(
            f"Collection '{name}' expects {vectors.size}-dim vectors but the active embedding "
            f"model produces {dim}. Re-run with --wipe or switch back to the original model."
        )


def run_universal_ingestion(base_dir: str, explicit_source_type: str | None = None, wipe: bool = False):
    """
    Scan base_dir, map sub-folders to source types, and ingest all documents.
    - Default: each sub-folder name becomes the source_type (e.g. data/hr/ -> "hr").
    - explicit_source_type: ingest the files directly inside base_dir under that one type.
    - wipe: drop and recreate the Qdrant collection before ingestion.
    """
    with logfire.span("Universal ingestion", base_directory=base_dir):
        if not os.path.isdir(base_dir):
            logfire.warning(f"Base directory not found: {base_dir}")
            return

        ensure_collection(wipe=wipe)

        if explicit_source_type:
            process_directory(base_dir, source_type=explicit_source_type)
            return

        sub_dirs = sorted(
            d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))
        )
        
        if not sub_dirs:
            logfire.warning(f"No sub-folders found in {base_dir}.")
            return

        for folder in sub_dirs:
            process_directory(os.path.join(base_dir, folder), source_type=folder)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest documents into Qdrant")
    parser.add_argument("base_dir", help="Folder containing documents (or sub-folders per source type)")
    parser.add_argument("--source-type", default=None, help="Treat all files in base_dir as this type")
    parser.add_argument("--wipe", action="store_true", help="Drop and recreate the collection first")
    args = parser.parse_args()

    run_universal_ingestion(args.base_dir, explicit_source_type=args.source_type, wipe=args.wipe)