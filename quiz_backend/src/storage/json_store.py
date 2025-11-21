import json
import os
import tempfile
from typing import Optional, Dict, Any, List


DEFAULT_DATA_FILE = "./data/quizzes.json"


class QuizJsonStore:
    """
    A simple JSON file store for quizzes with safe atomic write operations.

    Data model:
    {
        "quizzes": [ { ...quiz dict... }, ... ]
    }
    """

    # PUBLIC_INTERFACE
    def __init__(self, path: Optional[str] = None) -> None:
        """
        Initialize the JSON store.

        - Determines the storage path from the provided argument, the QUIZ_DATA_FILE
          environment variable, or falls back to DEFAULT_DATA_FILE.
        - Ensures the parent directory exists.
        """
        env_path = os.getenv("QUIZ_DATA_FILE")
        self.path = os.path.abspath(path or env_path or DEFAULT_DATA_FILE)

        # Ensure parent directory exists
        parent_dir = os.path.dirname(self.path) or "."
        os.makedirs(parent_dir, exist_ok=True)

    # PUBLIC_INTERFACE
    def load_all(self) -> Dict[str, Any]:
        """
        Load and return the entire data structure from the JSON file.
        If the file does not exist, it will be created with the default structure.

        Returns:
            dict: The data in the form {"quizzes": [ ... ]}.
        """
        if not os.path.exists(self.path):
            default_data = {"quizzes": []}
            self._atomic_write(default_data)
            return default_data

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            # If the file is corrupted, reset to default structure to keep service functioning.
            data = {"quizzes": []}
            self._atomic_write(data)

        # Normalize structure
        if not isinstance(data, dict) or "quizzes" not in data or not isinstance(data["quizzes"], list):
            data = {"quizzes": []}
            self._atomic_write(data)

        return data

    # PUBLIC_INTERFACE
    def save_all(self, data: Dict[str, Any]) -> None:
        """
        Persist the provided data to the JSON file using an atomic write.

        Args:
            data (dict): The full data structure to persist.
        """
        # Basic validation
        if not isinstance(data, dict):
            raise ValueError("Data must be a dict")
        if "quizzes" not in data or not isinstance(data["quizzes"], list):
            raise ValueError("Data must contain 'quizzes' as a list")

        self._atomic_write(data)

    # PUBLIC_INTERFACE
    def add_quiz(self, quiz: Dict[str, Any]) -> Dict[str, Any]:
        """
        Append a quiz to the store and persist.

        Args:
            quiz (dict): Quiz object. Expected to contain an 'id' key for retrieval.

        Returns:
            dict: The same quiz object after persistence.
        """
        data = self.load_all()
        quizzes: List[Dict[str, Any]] = data.get("quizzes", [])
        quizzes.append(quiz)
        data["quizzes"] = quizzes
        self.save_all(data)
        return quiz

    # PUBLIC_INTERFACE
    def get_quiz(self, quiz_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a quiz by its identifier.

        Args:
            quiz_id (str): The quiz identifier.

        Returns:
            dict | None: The quiz dict if found, otherwise None.
        """
        data = self.load_all()
        for q in data.get("quizzes", []):
            if isinstance(q, dict) and str(q.get("id")) == str(quiz_id):
                return q
        return None

    # PUBLIC_INTERFACE
    def list_quizzes(self) -> List[Dict[str, Any]]:
        """
        Return the list of all quizzes.

        Returns:
            list[dict]: List of quiz dictionaries.
        """
        data = self.load_all()
        return list(data.get("quizzes", []))

    def _atomic_write(self, data: Dict[str, Any]) -> None:
        """
        Write JSON to a temporary file and atomically replace the target.

        This ensures that readers never see a partially-written file.
        """
        directory = os.path.dirname(self.path) or "."
        fd, tmp_path = tempfile.mkstemp(prefix=".quizzes.", suffix=".tmp", dir=directory, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(data, tmp_file, indent=2, ensure_ascii=False)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(tmp_path, self.path)
        finally:
            # If os.replace succeeded, tmp_path no longer exists; ignore errors
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
