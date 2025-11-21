import hashlib
import random
import re
import string
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict


# A compact English stopword list to improve keyword extraction without external deps.
_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "while", "as", "of", "in", "on", "for", "to", "from", "by",
    "with", "without", "at", "about", "into", "over", "after", "before", "between", "through", "during", "above",
    "below", "up", "down", "out", "off", "again", "further", "then", "once",
    "is", "am", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "doing",
    "have", "has", "had", "having",
    "he", "she", "it", "they", "them", "his", "her", "its", "their", "theirs", "you", "your", "yours", "i", "we", "our", "ours",
    "this", "that", "these", "those", "there", "here", "such",
    "can", "could", "should", "would", "may", "might", "must", "will", "shall",
    "not", "no", "nor", "only", "own", "same", "so", "than", "too", "very",
    "what", "which", "who", "whom", "where", "when", "why", "how",
}

_SENTENCE_SPLIT_REGEX = re.compile(r"(?<=[.!?])\s+")
_TOKEN_REGEX = re.compile(r"[A-Za-z]+")


@dataclass
class Candidate:
    """Internal term candidate with frequency and examples of sentences."""
    term: str
    freq: int
    sentences: List[str]


def _stable_hash(text: str) -> str:
    """Return a stable hex digest for the input text."""
    # Using SHA256 for stability and uniformity
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _seed_from_hash(hex_digest: str) -> int:
    """Derive a deterministic integer seed from a hex digest."""
    # Take the first 16 hex chars for a 64-bit int
    return int(hex_digest[:16], 16)


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences using simple regex heuristics."""
    text = text.strip()
    if not text:
        return []
    parts = _SENTENCE_SPLIT_REGEX.split(text)
    # Clean trailing punctuation-only fragments
    sentences = [s.strip() for s in parts if s and any(c.isalnum() for c in s)]
    return sentences


def _tokenize_alpha(text: str) -> List[str]:
    """Extract alphabetical tokens (lowercased)."""
    return [m.group(0).lower() for m in _TOKEN_REGEX.finditer(text)]


def _collect_candidates(sentences: List[str]) -> List[Candidate]:
    """Collect term candidates based on frequency across the entire notes."""
    freq: Dict[str, int] = {}
    examples: Dict[str, List[str]] = {}
    for sent in sentences:
        tokens = _tokenize_alpha(sent)
        for t in tokens:
            if t in _STOPWORDS or len(t) <= 2:
                continue
            freq[t] = freq.get(t, 0) + 1
            if t not in examples:
                examples[t] = [sent]
            elif len(examples[t]) < 3:
                # Keep up to 3 example sentences where the term appears
                examples[t].append(sent)
    candidates = [Candidate(term=k, freq=v, sentences=examples.get(k, [])) for k, v in freq.items()]
    # Sort by frequency desc, then term asc for stability
    candidates.sort(key=lambda c: (-c.freq, c.term))
    return candidates


def _pick_distractors(all_terms: List[str], correct: str, rng: random.Random, n: int) -> List[str]:
    """Pick n distinct distractors from the pool, avoiding the correct term and duplicates."""
    pool = [t for t in all_terms if t != correct]
    # For short pools, fallback to slight variations to ensure 3 distractors
    if len(pool) < n:
        # Create pseudo-distractors by simple transforms of the correct answer
        variants = set(pool)
        base = correct
        while len(variants) < n:
            if len(base) > 3:
                variants.add(base[::-1])  # reversed
                variants.add(base + rng.choice(["", "s", "ed", "ing"]))
                variants.add(base.capitalize())
            else:
                variants.add(base + rng.choice(["1", "2", "3", "x"]))
            # Ensure we don't loop forever
            if len(variants) > 10 * n:
                break
        pool = list(variants)
    rng.shuffle(pool)
    return pool[:n]


def _make_fill_in_question(term: str, sentence: str) -> Tuple[str, str]:
    """Create a fill-in-the-blank style question from a sentence containing the term."""
    # Replace exact term occurrences (case-insensitive) with blank
    pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
    blanks = pattern.sub("_____", sentence)
    # Trim if sentence is extremely long
    if len(blanks) > 220:
        blanks = blanks[:217].rstrip() + "..."
    q = f"In the context of the notes, which term best completes the blank: '{blanks}'?"
    return q, term


def _make_definition_like_question(term: str, support_sentence: str) -> Tuple[str, str]:
    """Create a definition-like question using a supporting sentence."""
    snippet = support_sentence.strip()
    if len(snippet) > 220:
        snippet = snippet[:217].rstrip() + "..."
    q = f"Which term is most closely described by: '{snippet}'?"
    return q, term


def _sanitize_option(text: str) -> str:
    """Sanitize option text by collapsing whitespace and trimming."""
    t = " ".join(text.split())
    # Strip surrounding punctuation-only chars
    return t.strip(string.punctuation + " ")


def _unique_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        if it in seen:
            continue
        seen.add(it)
        out.append(it)
    return out


# PUBLIC_INTERFACE
def generate_quiz_from_notes(notes: str, title: Optional[str] = None) -> Dict:
    """
    Generate a deterministic multiple-choice quiz from study notes.

    Determinism:
        We compute a stable SHA-256 hash of the notes and seed a local RNG from it.
        All randomness (term selection, option shuffling) is driven by this RNG,
        making output stable for identical input.

    Heuristics:
        - Split into sentences.
        - Extract candidate key terms via frequency (alpha tokens, stopwords removed).
        - Generate 5-8 questions (based on candidate availability), each with 4 options.
        - Correct option drawn from context; other options sampled as distractors.
        - Options are shuffled with the seeded RNG and correct_index recorded.

    Args:
        notes: The raw notes text.
        title: Optional title to associate with the quiz. If None, we derive one.

    Returns:
        dict: Quiz structure compatible with API schemas. Contains:
              {
                "id": <quiz id>,
                "title": <title>,
                "created_at": <ISO-like string>,
                "source_notes_hash": <sha256 hex>,
                "questions": [
                    {
                      "id": <q id>,
                      "question": <question text>,
                      "options": [<4 strings>],
                      "correct_index": <int 0..3>
                    }, ...
                ]
              }
    """
    notes = (notes or "").strip()
    # Base hash drives determinism
    src_hash = _stable_hash(notes)
    rng = random.Random(_seed_from_hash(src_hash))

    # Split and extract candidates
    sentences = _split_sentences(notes)
    candidates = _collect_candidates(sentences)

    # Decide number of questions between 5 and 8 depending on candidates
    max_questions = 8
    min_questions = 5
    desired = min(max(len(candidates), min_questions), max_questions)
    num_questions = max(min_questions, min(desired, len(candidates))) if candidates else min_questions

    # If insufficient candidates, fabricate pseudo terms from frequent tokens
    if not candidates:
        # Build tokens from sentences as a fallback
        tokens = _tokenize_alpha(notes)
        tokens = [t for t in tokens if t not in _STOPWORDS and len(t) > 2]
        # If still empty, fallback to generic placeholders
        if not tokens:
            tokens = [f"Concept{i}" for i in range(1, 12)]
        # Create pseudo candidates
        freq: Dict[str, int] = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        sorted_tokens = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
        candidates = [Candidate(term=t, freq=f, sentences=[notes]) for t, f in sorted_tokens[:12]]

    # Pool of all unique terms for distractors
    all_terms = [c.term for c in candidates]
    all_terms = _unique_preserve_order(all_terms)

    # Pick candidate subset deterministically
    picked = candidates[:]
    rng.shuffle(picked)
    picked = picked[:num_questions]

    # Build questions
    questions = []
    for idx, cand in enumerate(picked, start=1):
        # Choose a supporting sentence: prefer one containing the term
        if cand.sentences:
            support = rng.choice(cand.sentences)
        else:
            support = rng.choice(sentences) if sentences else notes

        # Alternate question styles to add variety
        if idx % 2 == 1:
            q_text, correct = _make_fill_in_question(cand.term, support)
        else:
            q_text, correct = _make_definition_like_question(cand.term, support)

        # Build options: correct + distractors
        distractors = _pick_distractors(all_terms, correct, rng, 3)
        raw_options = [correct] + distractors
        options = [_sanitize_option(o) for o in raw_options if o and o.strip()]
        # Ensure we have exactly 4 options; pad if necessary
        while len(options) < 4:
            options.append(_sanitize_option(correct + rng.choice(["", "s", "ed", "ing"])))
        options = options[:4]

        # Remove duplicates while preserving first occurrence (ensure correct remains)
        options = _unique_preserve_order(options)
        while len(options) < 4:
            # Add synthetic options if dedup removed some
            synth = correct + rng.choice(["", "s", "ed", "ing", "ity", "ness"])
            if synth not in options:
                options.append(synth)

        # Shuffle options deterministically and compute correct index
        indices = list(range(len(options)))
        rng.shuffle(indices)
        shuffled = [options[i] for i in indices]
        correct_index = shuffled.index(correct) if correct in shuffled else 0

        questions.append(
            {
                "id": f"q-{idx}",
                "question": q_text,
                "options": shuffled,
                "correct_index": int(correct_index),
            }
        )

    # Title derivation
    derived_title = title.strip() if title else None
    if not derived_title:
        # Use top two frequent terms for a lightweight title
        top_terms = [c.term.capitalize() for c in candidates[:2]]
        derived_title = "Quiz: " + (" & ".join(top_terms) if top_terms else "Study Notes")

    # Created at: deterministic pseudo timestamp string based on hash to avoid external deps
    # Format: YYYY-MM-DDTHH:MM:SSZ where components are derived from hash bytes
    hbytes = bytes.fromhex(src_hash[:16])  # 8 bytes
    y = 2000 + (hbytes[0] % 30)  # 2000-2029
    mo = 1 + (hbytes[1] % 12)
    d = 1 + (hbytes[2] % 28)
    hh = hbytes[3] % 24
    mm = hbytes[4] % 60
    ss = hbytes[5] % 60
    created_at = f"{y:04d}-{mo:02d}-{d:02d}T{hh:02d}:{mm:02d}:{ss:02d}Z"

    quiz_id = f"quiz-{src_hash[:12]}"

    quiz = {
        "id": quiz_id,
        "title": derived_title,
        "created_at": created_at,
        "source_notes_hash": src_hash,
        "questions": questions,
    }
    return quiz
