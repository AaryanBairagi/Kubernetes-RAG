import logfire
from unstructured.partition.auto import partition


def parse_office(file_path : str) -> str :
    """
    Parses office documents like .docx , .pptx
    Unlike HTML these are structures and lightweight, hence easier to process locally 
    """
    with logfire.span("Office Parsing.." , filename="file_path"):
        try:
            elements = partition(filename = file_path)
            full_text = "\n".join(str[el] for el in elements)

            if not full_text.strip():
                logfire.warning(f"Unstructured returned empty text for file {file_path}")

            else :
                logfire.info(f"Successfully parsed file {file_path}")
                
            return full_text

        except Exception as e :
            logfire.error(f"Office Parsing Error.. {e}")
            raise e
