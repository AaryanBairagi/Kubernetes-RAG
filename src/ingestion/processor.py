import os
import logfire
import json
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models
from config import settings
from src.ingestion.chunking.splitter import chunk_text
from src.ingestion.loaders.office import parse_office
from src.ingestion.loaders.pdf import parse_pdf
from src.ingestion.loaders.text import parse_text
from src.ingestion.loaders.html import html_parser

logfire.configure(service_name = "enterprise-rag-app")


qd_client = QdrantClient(
    url = settings.QDRANT_URL,
    api_key = settings.QDRANT_API_KEY
)


PROCESSED_DATA_DIR = "processed_data"

def save_processed_metadata_locally(data : dict ,filename : str, source_type : str):
    """Save parsed chunk metadata as JSON in processed_data/<source_type>/."""
    folder = os.path.join(PROCESSED_DATA_DIR , source_type)
    os.makedirs(folder , exists_ok=True)
    dest = os.path.join(folder , f"{filename}.json")
    with open(dest , "w" , encoding = "utf-8") as f:
        json.dump(data , f , ensure_ascii = False , indent = 2)
    return dest
    

def process_file(file_path : str , filename : str , source_type : str):
    """Parse -> Chunk -> Save Locally -> Embed -> Save Qdrant Cloud"""
    with logfire.span("Processing the file.." , file = filename , source = source_type):
        try:
            #1.Process the files to extract text
            file_extension = filename.lower.rsplit('.' , 1)[-1] #split the path from right side look for . and only element needed so returns "pdf"

            if file_extension == "pdf":
                full_text = parse_pdf(file_path=file_path)

            elif file_extension in ("html","htm"):
                full_text = html_parser(file_path=file_path)

            elif file_extension in ("docx","pptx"):
                full_text = parse_office(file_path=file_path)

            elif file_extension == "txt":
                full_text = parse_text(file_path=file_path)

            else:
                logfire.warning(f"Skipping unsuported file type : {filename}")
                return 

            if not full_text or not full_text.strip():
                logfire.warning(f"No text extracted from the file : {filename}. Skipping")
                return

            #2.Chunk the extracted text
            chunks = chunk_text(full_text)
            if not chunks:
                logfire.warning("Chunks did not form for the extracted text")
                return

            #3.Save data locally
            processed_metadata = {
                "filename" : filename,
                "source_type" : source_type,
                "chunks" : chunks
            }

            local_path = save_processed_data_locally(source_type=source_type , filename=filename , chunks = chunks)
            logfire.info(f"Saved the data locally at path : {local_path}")

        except Exception as e:
            logfire.error("Error occurred while creating chunks : {e}")
            print("Error occurred while creating chunks : {e}")


def process_directory(dir_path : str , source_type : str):
    """Process every file in the directory"""
    



def run_universal_ingestion():
    pass