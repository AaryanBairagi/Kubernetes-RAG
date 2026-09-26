from bs4 import BeautifulSoup
import logfire

def html_parser(file_path : str) -> str:
    """
    Parses HTML content using BeautifulSoup
    Cleans scripts , sryles and extracts readable words for RAG
    """
    with logfire.span("HTML Parsing.." , filename = file_path):
        try:
            with open(file = file_path , encoding = "utf-8") as file:
                content = file.read()

            soup = BeautifulSoup(content , "html.parser")

            #Remove Junk
            for script in soup.find_all(["script" , "style" , "meta" , "noscript"]) :
                script.decompose()

            #Extract Text
            text = soup.get_text(separator = "\n")
            lines = (line.strip() for line in text.splitlines())

            chunks = (words for line in lines for words in line.split(" ")) #produces words form sentences

            text_clean = '\n'.join(chunk for chunk in chunks if chunk) #removes empty strings

            logfire.info(f"Successfully parsed the HTML file {file_path}")
            return text_clean

        except Exception as e :
            logfire.error(f"HTML Parse failed {e}")
            raise e
