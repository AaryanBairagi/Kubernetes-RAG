import logfire
from pypdf import PdfReader

def parse_pdf(file_path : str) -> str : 
    """ Extract text from a PDF locally using pypdf. 
    Falls back to pdfplumber for pages that yield no text 
    (e.g. image-heavy pages). """

    with logfire.span("PDF Parsing.." , filename = file_path) :
        try:
            reader = PdfReader(file_path)
            total_pages = len(reader.pages)
            logfire.info(f"PDF has total {total_pages} pages.")

            text_parts : list[str] = [] #to extract the actual text data
            blank_pages : list[str] = [] #to store the blank page number which pypdf couldnt extract

            for i , page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    text_parts.append(text)
                else:
                    blank_pages.append(i+1)

            if blank_pages:
                logfire.info("Blank pages found in the pdf")

                try:
                    import pdfplumber
                    with pdfplumber.open(file_path) as pdf:
                        for page_num in blank_pages:
                            page = pdf.pages[page_num - 1]
                            text = page.extract_text() or ""

                            if text.strip():
                                text_parts.append(text)
                            
                except Exception as plumber_err : 
                    logfire.warning(f"pdfplumber fallback failed: {plumber_err}")

            full_text = "\n".join(part for part in text_parts)

            if not full_text.strip():
                logfire.warning(f"No text extracted from {file_path}. File may be fully image-based.")

            else : 
                logfire.info(f"Extracted {len(full_text)} characters from {file_path}.")

            return full_text
        except Exception as e:
            logfire.error(f"PDF parsing failed {e}")
            raise e




