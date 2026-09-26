import logfire

def parse_text(file_path : str) -> str:
    """
    Parses the plain text files.
    """
    with logfire.span("Parsing Text file..." , filename = file_path) :
        try :   
            with open(file = file_path , encoding = 'utf-8' , errors = 'ignore') as file:
                return file.read()

        except Exception as e:
            logfire.error("Text file parsing failed..")
            raise e