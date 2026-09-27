from bs4 import BeautifulSoup
import logfire


def html_parser(file_path: str) -> str:
    """
    Parses HTML content using BeautifulSoup.
    Removes scripts, styles and other non-content tags, and extracts readable text for RAG.
    """
    with logfire.span("HTML Parsing..", filename=file_path):
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as file:
                content = file.read()

            soup = BeautifulSoup(content, "html.parser")

            # Remove junk
            for tag in soup.find_all(["script", "style", "meta", "noscript"]):
                tag.decompose()

            # Extract text, one line per text block
            text = soup.get_text(separator="\n")
            lines = (line.strip() for line in text.splitlines())

            text_clean = "\n\n".join(line for line in lines if line)

            logfire.info(f"Successfully parsed the HTML file {file_path}")
            return text_clean

        except Exception as e:
            logfire.error(f"HTML parse failed for {file_path}: {e}")
            raise