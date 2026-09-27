import os
import dotenv

dotenv.load_dotenv()

class Settings:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GROQ_MODEL = "llama-3.3-70b-versatile"
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
    QDRANT_URL = os.getenv("QDRANT_CLUSTER_ENDPOINT")
    QDRANT_COLLECTION = "enterprise-rag"

    REQUIRED = ("QDRANT_URL", "QDRANT_API_KEY")

    def validate(self) -> None:
        """Fail fast with a clear message if required .env values are missing."""
        missing = [name for name in self.REQUIRED if not getattr(self, name)]
        if missing:
            raise RuntimeError(f"Missing required settings (check your .env): {', '.join(missing)}")


settings = Settings()