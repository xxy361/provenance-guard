# Provenance Guard

A backend system that any creative sharing platform could plug into to classify submitted content, score confidence in that classification, surface a transparency label to users, and handle appeals from creators who believe they've been misclassified.

## 1. Overview

<!-- Project Structure-->

## 2. Tools and Setup

|Component|Tool|Notes|
|---|---|---|
|API framework|Flask|Free, lightweight|
|Detection signal 1|Groq (`llama-3.3-70b-versatile`)|Free tier — same account as Projects 1–3|
|Detection signal 2|Stylometric heuristics|Pure Python, no external libraries needed|
|Rate limiting|`Flask-Limiter`|Free|
|Audit log|SQLite (built-in) or structured JSON|No additional setup|

- Dependencies: `pip install -r requirements.text`
- Set up `GROQ_API_KEY` in `.env`
- Run the dev server: `flask --app app run` (port 5000).

## 3. Architecutre

## 4. Features

## 5. Edge Cases & Known Limitations

## 6. AI Tool Plan

## 7. Documentation

By order of implementation.

### M3: LLM Signal + Audit Log

LLM Signal Test:
```
curl -s -X POST http://127.0.0.1:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "The sun dipped below the horizon, painting the sky in hues of amber and rose. I sat on the porch, coffee in hand, watching the neighborhood slowly go quiet.", "creator_id": "test-user-1"}' | python -m json.tool
```

Output:
```
{
    "attribution": null,
    "confidence": null,
    "content_id": "2a1dc3d0-aa70-40bb-8840-568df6ab3f3b",
    "label": null,
    "signals": {
        "llm_reasoning": "The text's descriptive and personal tone suggests human authorship.",
        "llm_score": 0.2,
        "stylometric_score": null
    }
}
```

Audit Log test:
```
curl -s http://127.0.0.1:5000/log | python -m json.tool
```

Output:
```
{
    "entries": [
        {
            "content_id": "2a1dc3d0-aa70-40bb-8840-568df6ab3f3b",
            "creator_id": "test-user-1",
            "content_text": "The sun dipped below the horizon, painting the sky in hues of amber and rose. I sat on the porch, coffee in hand, watching the neighborhood slowly go quiet.",
            "create_ts": "2026-07-01T03:00:06.586464+00:00",
            "llm_score": 0.2,
            "llm_reasoning": "The text's descriptive and personal tone suggests human authorship.",
            "stylometric_score": null,
            "attribution": null,
            "confidence": null,
            "status": "classified",
            "creator_reasoning": null,
            "appeal_ts": null
        }
    ]
}
```
*attribution, confidence, label, second signals are placeholders in M3*

### M4: Stylometric Signal + Combined Scoring

**Same test from M3**
```
{
    "content_id": "0fc29f09-a0e3-4eae-9d6d-d5db9f703733",
    "attribution": "likely_human",
    "confidence": 0.32,
    "label": null,
    "signals": {
        "llm_score": 0.2,
        "llm_reasoning": "The text's descriptive and personal tone suggests human authorship.",
        "stylometric_score": 0.5
    }
}
```
Stylo score is uncertain, while LLM score is human.

**Clearly AI-generated (should score high)**
```
curl -s -X POST http://127.0.0.1:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment.", "creator_id": "test-user-2"}' | python -m json.tool
```

```
{
    "content_id": "3dc0dfda-e9ca-4dea-bb41-fd73fb06f928",
    "attribution": "likely_ai",
    "confidence": 0.7292442466843482,
    "label": null,
    "signals": {
        "llm_score": 0.9,
        "llm_reasoning": "The text's formal vocabulary and balanced perspective suggest AI authorship.",
        "stylometric_score": 0.47311061671087035
    }
}
```
  
**Clearly human-written (should score low)**
```
curl -s -X POST http://127.0.0.1:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. my friend got the spicy version and said it was better. probably wont go back unless someone drags me there", "creator_id": "test-user-2"}' \
  | python -m json.tool
```

```
{
    "content_id": "44762c1a-808f-4b30-a3a6-d82edbf95c7d",
    "attribution": "likely_human",
    "confidence": 0.2127780577395992,
    "label": null,
    "signals": {
        "llm_score": 0.1,
        "llm_reasoning": "The text contains informal language, personal opinions, and specific details, indicating a human writer.",
        "stylometric_score": 0.381945144348998
    }
}
```

**Borderline: formal human writing (may score mid-high on stylometrics)**
``` 
curl -s -X POST http://127.0.0.1:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "The relationship between monetary policy and asset price inflation has been extensively studied in the literature. Central banks face a fundamental tension between their mandate for price stability and the unintended consequences of prolonged low interest rates on equity and real estate valuations.", "creator_id": "test-user-2"}' | python -m json.tool
```

```
{
    "content_id": "220d9b39-d1d1-48fb-850f-ab6936393008",
    "attribution": "uncertain",
    "confidence": 0.686370739588744,
    "label": null,
    "signals": {
        "llm_score": 0.8,
        "llm_reasoning": "The text's formal vocabulary and balanced discussion suggest AI authorship.",
        "stylometric_score": 0.51592684897186
    }
}
```

**Borderline: lightly edited AI output (should ideally score mid-range)**
```
curl -s -X POST http://127.0.0.1:5000/submit \
  -H "Content-Type: application/json" \
  -d '{"text": "I'\''ve been thinking a lot about remote work lately. There are genuine tradeoffs — flexibility and no commute on one side, isolation and blurred work-life boundaries on the other. Studies show productivity varies widely by individual and role type.", "creator_id": "test-user-2"}' | python -m json.tool
```

```
{
    "content_id": "28b459eb-2ebe-4a14-a412-e4d1033f9494",
    "attribution": "uncertain",
    "confidence": 0.62,
    "label": null,
    "signals": {
        "llm_score": 0.7,
        "llm_reasoning": "The text's balanced and generic discussion of remote work, using phrases like 'on the other side', suggests AI influence.",
        "stylometric_score": 0.5
    }
}
```

