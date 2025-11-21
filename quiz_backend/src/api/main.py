import os
from functools import lru_cache

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from src.storage.json_store import QuizJsonStore

# Load environment variables from a .env file if present
load_dotenv()

app = FastAPI(
    title="Study Notes Quiz Backend",
    description="Backend service for generating and storing quizzes from study notes.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# PUBLIC_INTERFACE
def get_store() -> QuizJsonStore:
    """Return a cached singleton instance of the quiz JSON store."""
    return _get_store_singleton()


@lru_cache(maxsize=1)
def _get_store_singleton() -> QuizJsonStore:
    """
    Internal cached constructor for the store. Uses QUIZ_DATA_FILE if set,
    otherwise defaults to './data/quizzes.json'.
    """
    path = os.getenv("QUIZ_DATA_FILE")
    return QuizJsonStore(path=path)


@app.get("/", summary="Health Check", tags=["System"])
def health_check():
    """
    Health check endpoint.

    Returns:
        JSON payload with a simple 'Healthy' message and the current data file path.
    """
    # Touch the store to ensure file/dir is created on startup
    store = get_store()
    # Load ensures file exists with default structure
    _ = store.load_all()
    return {"message": "Healthy", "data_file": store.path}
