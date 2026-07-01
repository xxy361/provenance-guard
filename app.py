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

from db import get_log, init_log, submit_log
from detection.llm_signal import llm_signal

app = Flask(__name__)
app.json.sort_keys = False  # preserve insertion order (audit_log column order) in responses
init_log(app)


@app.route("/submit", methods=["POST"])
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

    # TODO Signal 2: stylometric heuristics -> stylometric_score
    # TODO combine into calibrated confidence score (false-positive-averse)
    # TODO map confidence -> three-category transparency label
    stylometric_score = None
    confidence = None
    attribution = None
    label = None

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
