"""Signal 1: LLM classification.

Holistic semantic/stylistic assessment of whether text reads as human- or
AI-written, via the Groq LLM. Higher scores mean more likely AI.
"""

import json

from groq import Groq

import config

client = Groq(api_key=config.GROQ_API_KEY)

LLM_SYSTEM_PROMPT = """\
You are a forensic writing analyst. Given a piece of text, judge how likely it \
is that the text was written by an AI language model rather than a human.

Look at the text from a SEMANTIC perspective:
- Human writing tends to be personal, opinionated, specific, and unpredictable. \
It may jump topics, take a clear stance, and contain imperfect grammar or messy, \
informal language.
- AI writing tends to be generic, impersonal, and balanced ("on the other hand", \
"however"), tightly focused on one topic, smooth and tidy, and sometimes uses \
overly formal vocabulary for the context ("furthermore", "moreover").

Respond with ONLY a JSON object, no extra text, in exactly this form:
{"llm_score": <float 0.0-1.0>, "llm_reasoning": "<one short sentence>"}

llm_score is the probability the text is AI-written: 0.0 = clearly human, \
1.0 = clearly AI. llm_reasoning is a single concise line explaining the score.
"""


def llm_signal(text):
    """Signal 1 — holistic semantic/stylistic classification via Groq LLM.

    Args:
        text: the raw text submitted by the creator.

    Returns:
        (llm_score, llm_reasoning): a float in [0, 1] where higher means more
        likely AI-written, and a one-line human-readable rationale.

    Note: the LLM is non-deterministic, so the score carries inherent
    uncertainty; it may also flag genuinely human text that happens to read
    like AI. The combined confidence scorer accounts for this.
    """
    completion = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    raw = completion.choices[0].message.content
    data = json.loads(raw)

    score = float(data["llm_score"])
    score = max(0.0, min(1.0, score))  # clamp defensively
    reasoning = str(data.get("llm_reasoning", "")).strip()

    return score, reasoning
