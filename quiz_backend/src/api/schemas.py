from typing import List, Optional
from pydantic import BaseModel, Field


# PUBLIC_INTERFACE
class NoteIn(BaseModel):
    """Input model for submitting notes to generate a quiz."""
    title: Optional[str] = Field(default=None, description="Optional title for the generated quiz.")
    notes: str = Field(..., description="Raw study notes text used for quiz generation.")


# PUBLIC_INTERFACE
class QuizQuestion(BaseModel):
    """A single multiple-choice question."""
    id: str = Field(..., description="Stable identifier for the question within the quiz.")
    question: str = Field(..., description="Question prompt text.")
    options: List[str] = Field(..., description="List of 4 answer options (strings).")
    correct_index: int = Field(..., description="Index of the correct option within the options list (0-based).")


# PUBLIC_INTERFACE
class QuizOut(BaseModel):
    """Full quiz payload returned after generation or retrieval."""
    id: str = Field(..., description="Unique identifier for the quiz set.")
    title: str = Field(..., description="Title of the quiz.")
    created_at: str = Field(..., description="Creation timestamp (string format).")
    source_notes_hash: str = Field(..., description="Stable SHA-256 hex digest of the source notes content.")
    questions: List[QuizQuestion] = Field(..., description="List of generated quiz questions.")


# PUBLIC_INTERFACE
class QuizMetaOut(BaseModel):
    """Metadata view of a quiz for listing endpoints."""
    id: str = Field(..., description="Unique identifier for the quiz set.")
    title: str = Field(..., description="Title of the quiz.")
    created_at: str = Field(..., description="Creation timestamp (string format).")
    question_count: int = Field(..., description="Number of questions contained in the quiz.")
