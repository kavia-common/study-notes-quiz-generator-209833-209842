"""
API package initialization.

Exports shared schema models for external use.
"""

# Re-export commonly used schema models
from .schemas import NoteIn, QuizQuestion, QuizOut, QuizMetaOut  # noqa: F401
