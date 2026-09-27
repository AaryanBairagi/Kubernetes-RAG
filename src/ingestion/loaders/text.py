import logfire


def parse_text(file_path: str) -> str:
    """
    Parses plain text files.
    """
    with logfire.span("Parsing Text file...", filename=file_path):
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as file:
                return file.read()

        except Exception as e:
            logfire.error(f"Text file parsing failed for {file_path}: {e}")  
            raise