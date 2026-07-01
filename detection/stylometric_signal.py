"""Signal 2: Stylometric heuristics.

Pure-Python statistical assessment of *how* the text is structured, independent
of what it says. AI writing trends smooth and uniform; human writing trends
irregular and messy. Higher scores mean more likely AI.

This signal is deliberately noisy on short or formally-structured texts (see
blind spots in planning.md); the combined confidence scorer weights it below the
LLM signal and leans toward "uncertain" to guard against false positives.
"""

import re
import statistics

# Below this many words the structural signals are too noisy to trust, so we
# abstain and return the neutral midpoint rather than a confident guess.
MIN_WORDS_FOR_SIGNAL = 40

_SENTENCE_SPLIT = re.compile(r"[.!?]+")
_WORD = re.compile(r"[A-Za-z']+")


def _split_sentences(text):
    """Split into non-empty, stripped sentences on ., !, ? runs."""
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _burstiness_score(sentences):
    """Irregular sentence length = human. Uniform length = AI.

    Uses the coefficient of variation (stdev / mean) of sentence word-counts so
    the measure is scale-free. High variation -> human -> low AI score.
    """
    lengths = [len(_WORD.findall(s)) for s in sentences]
    lengths = [n for n in lengths if n > 0]
    if len(lengths) < 2:
        return 0.5

    mean = statistics.mean(lengths)
    if mean == 0:
        return 0.5
    cv = statistics.stdev(lengths) / mean

    # cv ~0.0 (perfectly uniform, very AI) -> 1.0; cv >=0.8 (bursty human) -> 0.0.
    return max(0.0, min(1.0, 1.0 - cv / 0.8))


def _lexical_diversity_score(words):
    """Type-token ratio. AI repeats a smoother, narrower vocabulary.

    TTR is length-sensitive, so measure it over a fixed window of the first
    `window` words to keep the comparison fair across texts of different sizes.
    """
    window = 100
    sample = words[:window]
    if not sample:
        return 0.5

    ttr = len(set(sample)) / len(sample)

    # ttr <=0.4 (repetitive, AI-like) -> 1.0; ttr >=0.75 (rich, human) -> 0.0.
    return max(0.0, min(1.0, (0.75 - ttr) / (0.75 - 0.4)))


def _punctuation_variety_score(text):
    """Messy, varied punctuation = human. Clean, plain punctuation = AI.

    Humans sprinkle in dashes, ellipses, parentheses, semicolons, and repeated
    marks ("!!", "..."); AI prose leans on plain periods and commas.
    """
    messy = len(re.findall(r"[;:\-—()\"'/]|\.{2,}|[!?]{2,}", text))
    words = _WORD.findall(text)
    if not words:
        return 0.5

    density = messy / len(words)

    # density 0 (clean, AI) -> 1.0; density >=0.12 (messy, human) -> 0.0.
    return max(0.0, min(1.0, 1.0 - density / 0.12))


def stylometric_signal(text):
    """Signal 2 — structural (stylometric) classification.

    Args:
        text: the raw text submitted by the creator.

    Returns:
        stylometric_score: a float in [0, 1] where higher means more likely
        AI-written, derived purely from structural statistics of the text.

    Short texts fall below `MIN_WORDS_FOR_SIGNAL` and return the neutral 0.5,
    since sentence-variance and vocabulary measures are unreliable there.
    """
    words = [w.lower() for w in _WORD.findall(text)]
    if len(words) < MIN_WORDS_FOR_SIGNAL:
        return 0.5

    sentences = _split_sentences(text)

    burstiness = _burstiness_score(sentences)
    diversity = _lexical_diversity_score(words)
    punctuation = _punctuation_variety_score(text)

    # Equal-weighted blend of the three structural cues. Sentence-length
    # regularity ("burstiness") is the strongest documented AI tell, but keeping
    # the weights uniform avoids overfitting a heuristic that only feeds 40% of
    # the final confidence anyway.
    score = (burstiness + diversity + punctuation) / 3.0
    return max(0.0, min(1.0, score))
