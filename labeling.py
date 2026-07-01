"""Transparency-label mapping.

Turns an attribution + confidence into the plain-language string a reader would
see on the platform. The three variants match planning.md § Transparency Label
(and README.md) verbatim. Scoring (combining signals into a confidence and
attribution) lives in detection/scoring.py; this module only does the wording.
"""


def label(attribution, confidence):
    """Map an attribution + confidence to a reader-facing transparency label.

    The confidence percentage is interpolated for the two high-confidence
    cases. `confidence` is the AI-likelihood in [0, 1]; the human label reports
    the complementary (1 - confidence) as its confidence.
    """
    if attribution == "likely_ai":
        return (
            f"The system found strong signs this text was produced by AI "
            f"({confidence * 100:.0f}% Confidence). If you wrote this "
            f"yourself, please submit an appeal request."
        )
    if attribution == "likely_human":
        return (
            f"The system found this text reads as human-written "
            f"({(1 - confidence) * 100:.0f}% Confidence). This is an "
            f"automated estimate, not a guarantee."
        )
    return (
        "The system found mixed patterns of both human and AI writing. "
        "Analysis is inconclusive."
    )