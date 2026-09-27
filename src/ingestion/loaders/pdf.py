import logfire
from pypdf import PdfReader


def parse_pdf(file_path: str) -> str:
    """
    Extract text from a PDF locally using pypdf.
    Falls back to pdfplumber for pages that yield no text.
    Note: neither library does OCR, so fully image-based pages stay empty.
    """
    with logfire.span("PDF Parsing..", filename=file_path):
        try:
            reader = PdfReader(file_path)
            total_pages = len(reader.pages)
            logfire.info(f"PDF has {total_pages} pages.")

            page_texts: list[str] = [""] * total_pages
            blank_pages: list[int] = []  

            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    page_texts[i] = text
                else:
                    blank_pages.append(i)

            if blank_pages:
                logfire.info(f"{len(blank_pages)} page(s) empty with pypdf, trying pdfplumber")
                try:
                    import pdfplumber

                    with pdfplumber.open(file_path) as pdf:
                        for i in blank_pages:
                            text = pdf.pages[i].extract_text() or ""
                            if text.strip():
                                page_texts[i] = text
                except Exception as plumber_err:
                    logfire.warning(f"pdfplumber fallback failed: {plumber_err}")

            full_text = "\n\n".join(t for t in page_texts if t.strip())

            if not full_text.strip():
                logfire.warning(f"No text extracted from {file_path}. File may be fully image-based.")
            else:
                logfire.info(f"Extracted {len(full_text)} characters from {file_path}.")

            return full_text

        except Exception as e:
            logfire.error(f"PDF parsing failed for {file_path}: {e}")
            raise