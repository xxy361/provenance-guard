"""Confidence scoring and transparency-label mapping.

Combines the two signal scores into one calibrated 0-1 confidence (higher =
more likely AI) and maps it to one of three attribution categories. The mapping
is deliberately *not* a binary flip at 0.5: there is a wide "uncertain" band,
skewed so that it takes stronger evidence to call something AI than to call it
human. This encodes the rubric's priority that false positives — flagging a
human's work as AI — are the worse error on a writing platform.
"""

import config


def score(llm_score, stylometric_score):
    """Combine the two signals into a single calibrated confidence.

    Args:
        llm_score: Signal 1 output in [0, 1], higher = more likely AI.
        stylometric_score: Signal 2 output in [0, 1], higher = more likely AI.

    Returns:
        (confidence, attribution): confidence is a float in [0, 1] where higher
        means more likely AI; attribution is one of "likely_ai", "uncertain",
        or "likely_human".

    The LLM signal carries more weight because stylometric heuristics are
    noisier (short or formally-structured human text reads as uniform), while
    semantic and tonal cues are easier to judge. Weights and thresholds live in
    config.py and may be retuned during testing.
    """
    confidence = config.LLM_WEIGHT * llm_score + config.STYLO_WEIGHT * stylometric_score
    confidence = max(0.0, min(1.0, confidence))

    if confidence >= config.AI_THRESHOLD:
        attribution = "likely_ai"
    elif confidence < config.HUMAN_THRESHOLD:
        attribution = "likely_human"
    else:
        attribution = "uncertain"

    return confidence, attribution
