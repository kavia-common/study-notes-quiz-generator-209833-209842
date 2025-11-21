import os
from functools import lru_cache
from typing import List

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from src.storage.json_store import QuizJsonStore
from src.services.quiz_generator import generate_quiz_from_notes
from src.api.schemas import NoteIn, QuizOut, QuizMetaOut

# Load environment variables from a .env file if present
load_dotenv()

openapi_tags = [
    {"name": "System", "description": "System and service endpoints"},
    {"name": "Quizzes", "description": "Quiz generation and retrieval endpoints"},
]

app = FastAPI(
    title="Study Notes Quiz Backend",
    description="Backend service for generating and storing quizzes from study notes.",
    version="0.1.0",
    openapi_tags=openapi_tags,
)

# CORS configuration to allow frontend integration (adjust origins in env if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(",") if os.getenv("CORS_ALLOW_ORIGINS") else ["*"],
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


@app.post(
    "/notes",
    response_model=QuizOut,
    status_code=status.HTTP_201_CREATED,
    summary="Generate quiz from study notes",
    description="Accepts raw study notes and an optional title, generates a deterministic quiz, persists it, and returns the quiz.",
    tags=["Quizzes"],
)
def submit_notes(note_in: NoteIn) -> QuizOut:
    """
    Create a quiz from provided notes and persist it.

    Args:
        note_in: Pydantic model containing notes (str) and optional title (str).

    Returns:
        QuizOut: The generated quiz payload.

    Notes:
        - Deterministic generation ensures identical notes produce the same quiz ID and content.
        - The quiz is appended to the JSON store for later retrieval.
    """
    notes = (note_in.notes or "").strip()
    if not notes:
        raise HTTPException(status_code=400, detail="Notes content cannot be empty")

    quiz = generate_quiz_from_notes(notes=notes, title=note_in.title)
    store = get_store()

    # If a quiz with same id already exists, we still store another copy only if not already present.
    # To keep idempotency for same notes, avoid duplicate persist for same id.
    existing = store.get_quiz(quiz.get("id"))
    if existing is None:
        store.add_quiz(quiz)

    # Validate output matches schema shape implicitly via response_model
    return QuizOut(**quiz)


@app.get(
    "/quizzes",
    response_model=List[QuizMetaOut],
    summary="List quizzes",
    description="Returns a list of quiz metadata, including id, title, created_at, and question_count.",
    tags=["Quizzes"],
)
def list_quizzes() -> List[QuizMetaOut]:
    """
    List all stored quizzes.

    Returns:
        List[QuizMetaOut]: Collection of quiz metadata entries.
    """
    store = get_store()
    quizzes = store.list_quizzes()
    metas = [
        QuizMetaOut(
            id=q.get("id", ""),
            title=q.get("title", ""),
            created_at=q.get("created_at", ""),
            question_count=len(q.get("questions", []) or []),
        )
        for q in quizzes
        if isinstance(q, dict)
    ]
    # Sort newest first by created_at string (already stable-like)
    metas.sort(key=lambda m: m.created_at, reverse=True)
    return metas


@app.get(
    "/quizzes/{quiz_id}",
    response_model=QuizOut,
    summary="Get quiz by id",
    description="Returns the full quiz payload for the specified quiz identifier.",
    tags=["Quizzes"],
)
def get_quiz(quiz_id: str) -> QuizOut:
    """
    Retrieve a single quiz by identifier.

    Args:
        quiz_id: The quiz identifier (e.g., 'quiz-<hashprefix>').

    Returns:
        QuizOut: Full quiz payload.

    Raises:
        HTTPException 404 if the quiz is not found.
    """
    store = get_store()
    quiz = store.get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return QuizOut(**quiz)
