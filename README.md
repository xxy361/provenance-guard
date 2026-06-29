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
