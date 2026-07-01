"""Provenance Guard — Flask backend.

Classifies whether submitted text-based creative work is human- or AI-written,
scores confidence, surfaces a transparency label, and handles appeals.

This module holds the HTTP endpoints. Detection signals live in the
`detection` package; scoring, labeling, and the audit log are wired in as they
are built.

See docs/Provenance Guard.md for the authoritative spec and planning.md for the
architecture diagram.
"""

import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import labeling
from db import appeal_log, get_entry, get_log, init_log, submit_log
from detection import scoring
from detection.llm_signal import llm_signal
from detection.stylometric_signal import stylometric_signal

app = Flask(__name__)
app.json.sort_keys = False  # preserve insertion order (audit_log column order) in responses
init_log(app)

# Rate limiting: keyed by client IP, in-memory store for local dev. Limits are
# applied per-route (see /submit) rather than globally. See README § Rate
# Limiting for the justification of the chosen numbers.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


@app.errorhandler(429)
def ratelimit_exceeded(e):
    """Return over-limit responses as JSON instead of Flask-Limiter's HTML."""
    return jsonify({"error": f"rate limit exceeded: {e.description}"}), 429


@app.route("/submit", methods=["POST"])
@limiter.limit("10 per minute;100 per day")
def submit():
    """Accept text, run the detection pipeline, and return the classification.

    Expects JSON: {"text": <str>, "creator_id": <str>}
    Returns JSON: {content_id, attribution, confidence, label,
                   signals: {llm_score, stylometric_score}}
    """
    body = request.get_json(silent=True) or {}
    text = body.get("text")
    creator_id = body.get("creator_id")

    if not text or not isinstance(text, str) or not text.strip():
        return jsonify({"error": "'text' is required and must be a non-empty string"}), 400
    if not creator_id:
        return jsonify({"error": "'creator_id' is required"}), 400

    content_id = str(uuid.uuid4())

    # Signal 1: LLM
    llm_score, llm_reasoning = llm_signal(text)

    # Signal 2: stylometric heuristics
    stylometric_score = stylometric_signal(text)

    # Combine into a calibrated, false-positive-averse confidence + attribution
    confidence, attribution = scoring.score(llm_score, stylometric_score)

    # Map confidence -> three-category transparency label
    label = labeling.label(attribution, confidence)

    submit_log(
        {
            "content_id": content_id,
            "creator_id": creator_id,
            "content_text": text,
            "create_ts": datetime.now(timezone.utc).isoformat(),
            "llm_score": llm_score,
            "llm_reasoning": llm_reasoning,
            "stylometric_score": stylometric_score,
            "attribution": attribution,
            "confidence": confidence,
            "status": "classified",
            "creator_reasoning": None,
            "appeal_ts": None,
        }
    )

    return jsonify(
        {
            "content_id": content_id,
            "attribution": attribution,
            "confidence": confidence,
            "label": label,
            "signals": {
                "llm_score": llm_score,
                "llm_reasoning": llm_reasoning,
                "stylometric_score": stylometric_score,
            },
        }
    ), 200


@app.route("/appeal", methods=["POST"])
def appeal():
    """Accept a creator's appeal against a classification.

    Expects JSON: {"content_id": <str>, "creator_reasoning": <str>}
    Looks up the original decision by content_id, sets its status to
    "under_review", and records the creator's reasoning and appeal timestamp
    alongside the original entry in the audit log. Automated re-classification
    is out of scope — a human reviews the flagged entry later.

    Returns JSON: {content_id, status, message}
    """
    body = request.get_json(silent=True) or {}
    content_id = body.get("content_id")
    creator_reasoning = body.get("creator_reasoning")

    if not content_id:
        return jsonify({"error": "'content_id' is required"}), 400
    if not creator_reasoning or not isinstance(creator_reasoning, str) or not creator_reasoning.strip():
        return jsonify({"error": "'creator_reasoning' is required and must be a non-empty string"}), 400

    entry = get_entry(content_id)
    if entry is None:
        return jsonify({"error": f"no submission found for content_id {content_id!r}"}), 404
    if entry["status"] == "under_review":
        return jsonify({"error": f"an appeal for content_id {content_id!r} is already under review"}), 409

    appeal_log(content_id, creator_reasoning, datetime.now(timezone.utc).isoformat())

    return jsonify(
        {
            "content_id": content_id,
            "status": "under_review",
            "message": "Your appeal has been submitted and is under review.",
        }
    ), 200


@app.route("/log", methods=["GET"])
def log():
    """Return recent structured audit-log entries for grading visibility.

    Returns JSON: {entries: [ {creator_id, content_id, content_text,
    create_ts, llm_score, llm_reasoning, stylometric_score, attribution,
    confidence, status, creator_reasoning, appeal_ts}, ... ]}
    """
    return jsonify({"entries": get_log()}), 200


if __name__ == "__main__":
    app.run(port=5000, debug=True)
