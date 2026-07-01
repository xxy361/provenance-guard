# Provenance Guard — Planning

## 1. Overview

A backend system that any creative sharing platform could plug into to classify submitted content, score confidence in that classification, surface a transparency label to users, and handle appeals from creators who believe they've been misclassified.

### Implementation Plan

| Status | Milestone                                   | Delivers                                                               |
| ------ | ------------------------------------------- | ---------------------------------------------------------------------- |
| X      | **M1 — Understand & define architecture**   | architecture narrative, 2 signals + blind spots, API contract, diagram |
| X      | **M2 — Write the spec**                     | this `planning.md`                                                     |
| X      | **M3 — Submission endpoint + first signal** | Flask app, `POST /submit`, Groq signal, basic audit log, `GET /log`    |
| X      | **M4 — Second signal + scoring**            | stylometric signal, confidence scoring, both scores in the log         |
| X      | **M5 — Production layer**                   | transparency labels, `POST /appeal`, rate limiting, complete log       |
|        | **M6 — Document & walk through**            | README (all required sections)                                         |

## 2. Tools and Setup

| Component          | Tool                             | Notes                                  |
| ------------------ | -------------------------------- | -------------------------------------- |
| API framework      | Flask                            | the HTTP server exposing the endpoints |
| Detection signal 1 | Groq (`llama-3.3-70b-versatile`) | free tier; semantic read               |
| Detection signal 2 | Stylometric heuristics           | pure Python, no external libs          |
| Rate limiting      | `Flask-Limiter`                  | on `/submit`                           |
| Audit log + state  | SQLite                           | built-in; structured                   |

- Dependencies: `pip install -r requirements.txt`
- Set up `GROQ_API_KEY` in `.env`
- Run the dev server: `flask --app app run` (port 5000).

## 3. Architecture

### Submission Flow

The user sends a piece of text through the **submission endpoint** using `POST /submit` with a `creator_id` to record who submitted the text. The text first goes through **LLM (Signal 1)** to decide if it sounds human or AI and gets the first score. Then the same text goes through Python-programmed **stylometric heuristics (Signal 2)** and gets second score. The scores are then combined into one 0–1 **confidence score**, which the text would be **labeled** depending on the score. The **audit log** records the decision. Lastly, the attribution, confidence, and label are returned to the user as the **response**.

```
SUBMISSION
  client --{text, creator_id}--> POST /submit
     |--raw text--> Signal 1: Groq LLM ----score(0-1)--\
     |--raw text--> Signal 2: Stylometrics --score(0-1)--> Confidence Scorer
                                                                  |
                                                          combined score(0-1)
                                                                  |
                                                            Label Mapper --label text--\
                                                                  |                     |
                                                            Audit Log <--decision-------+
                                                                  |
     <--{content_id, attribution, confidence, label, signals}-- response
```

### Appeal Flow

The user can contest the classification using `POST /appeal`, with reasoning and a `content_id` to identify the text. The appeal will be logged in the **audit log** alongside the original decisions and have the status set to `under_review`. The user gets a **confirmation** that the appeal has been submitted. A reviewer would manually review and make a decision on the appeal (reclassification is not part of required features).

```
APPEAL
  client --{content_id, creator_reasoning}--> POST /appeal
     --> set status = under_review --> Audit Log (appeal entry) --> {confirmation}
```

## 4. Features

### Submission Endpoint

- **Purpose:** an API endpoint that accepts a piece of text-based content (a poem, a short story excerpt, a blog post) and return a structured response including the attribution result, confidence score, and the transparency label text that would be shown to the user.
- **Endpoints**: `POST /submit`
- **Accepts**: `{text, creator_id}` (a piece of text along with the user id)
- **Returns**: `{content_id, attribution, confidence, label, signals: {llm_score, stylometric_score}}` 
- **Decisions:** starts with generating a `content_id` which is a `uuid`. Then orchestrates the process of passing the text to signals, scoring, labeling, audit log writing, and responding back to the user. When the new record entered audit log, set `status` to `classified`

### Multi-Signal Detection

- **Purpose:** classify content using ≥2 genuinely distinct signals.
#### Signal 1: LLM

- **Accepts**: a `string` which is the text the user submitted through endpoint.
- **Returns**: a `llm_score` (`float`) between 0 - 1 and `llm_reasoning` (`string`) which is a one-line reasoning. Higher score means more likely AI.
- **Decisions**: measures human vs AI writing by looking at what the text says from a **semantic** perspective
	- Humans usually write more personal and opinionated text, which usually is more specific to the subject. Human writing is more unpredictable and can sometimes jump topics. Humans are likely to use imperfect grammar and messy language (at least on the Internet).
	- AI writing is generic, impersonal, and not opinionated, usually giving both sides or multiple stances on the subject (ex. "on the other hand", "however"). AI writing is more focused and predictable as they are usually tailored towards one specific topic (what the user asks for). AI also writes in a smoother and tidier way, sometimes use overly formal or unnatural vocabulary for the context (ex. "furthermore", "moreover").
- **Blind Spots**: LLM is non-deterministic which adds uncertainty to scoring. LLM could also flag text that sounds AI but actually written or edited by humans (LLMs are trained on human data, so it is possible that someone just writes like AI).

#### Signal 2: Stylometric Heuristics

- **Accepts**: a `string` which is the text the user submitted through endpoint.
- **Returns**: a `stylometric_score` (`float`) between 0 - 1. Higher score means more likely AI.
- **Decisions**: measures human vs AI writing by looking at how the text is **structured**.
	- Humans mixes short and long phases in an irregular way. In general, at least on the Internet, humans write very messy—with imperfect grammar, surprising choice of vocabulary, random and repeated use of symbols, and fragmented sentences.
	- AI writes in a smooth and consistent manner. Sentences are likely to have similar length and even rhythm.
- **Blind Spots**: could be unreliable on short texts. Could flag texts that is structurally similar to AI-generated text (ex. uniform, formal style). Also ignores the meaning of the text.

### Confidence Scoring & Uncertainty

- **Purpose:** combine the signals into one 0–1 confidence and map it to three label variants — never a binary flip at 0.5.
- **Accepts**: `(llm_score, stylometric_score)` from the signals
- **Returns**: `{confidence, attribution}` where `attribution` is `likely_ai` / `uncertain` / `likely_human`.
- **Decisions:**
	- **Combined Score:** `confidence =  LLM_WEIGHT × llm_score + STYLO_WEIGHT × stylometric_score`
		- Start with `LLM_WEIGHT = 0.6` and `STYLO_WEIGHT = 0.4`
		- Higher `confidence` score means more likely AI (ex. `confidence = 0.6` means 60% confidence of AI writing and 40% confidence of human writing)
		- These will be variables in the configuration file, might change upon testing
		- `LLM_WEIGHT + STYLO_WEIGHT = 1` to make sure `confidence` does not go above `1`
		- The LLM signal gets more weight because stylometric heuristics could have greater noise (short texts are common, consistently and evenly structured texts are common in formal writing), while semantic and tonal differences are easier to identify.
	- **False Positive Problem:** Consider that it is more likely a human writes similar to AI or edits AI-generated draft than an AI sounding naturally human, it is worse to flag a human writing as AI than mislabeling AI writing as human. In this case, it is better to label these kind of texts as "uncertain", and the system will have a wider uncertainty band towards the AI side than the human side. In those cases, the creator could submit an appeal. 
	- **Thresholds:** 
		- Start with `AI_THRESHOLD = 0.7` and `HUMAN_THRESHOLD = 0.4`
		- These will be variables in the configuration file, might change upon testing

| Confidence                 | Attribution    |
|----------------------------|----------------|
| `confidence ≥ 0.70`        | `likely_ai`    |
| `0.40 ≤ confidence < 0.70` | `uncertain`    |
| `confidence < 0.40`        | `likely_human` |

### Transparency Label

- **Purpose:** the label that would be displayed to a reader on the platform. It communicates the attribution result in plain language and make the confidence level meaningful to a non-technical reader
- **Design:**
	- **High-confidence AI**:  "The system found strong signs this text was produced by AI ({confidence * 100}% Confidence). If you wrote this yourself, please submit an appeal request."
	- **Uncertain**: "The system found mixed patterns of both human and AI writing. Analysis is inconclusive."
	- **High-confidence human**: "The system found this text reads as human-written ({(1- confidence) * 100}% Confidence). This is an automated estimate, not a guarantee."

### Appeals Workflow

- **Purpose:** a mechanism for creators to contest a classification. Automated re-classification is not required.
- **Endpoints**: `POST /appeal`
- **Accepts**: `{content_id, creator_reasoning}` (the user provides the look up id for the text they want to appeal for along with their reasoning)
- **Returns**: `{content_id, status: "under_review", message}` (a confirmation that appeal has been submitted)
- **Decisions:** 
	- look up the text to appeal by `content_id` in the audit log. The entry contains the original decision
	- set status from `classified` to `under_review`
	- fill in the `creator_reasoning` and `appeal_ts` columns which are originally `null`
	- a reviewer opening the queue sees the original text, attribution, both signal scores, combined confidence, the label shown, the creator's reasoning, and timestamps
- **Limitation:** in real practice, only the owner of the original text (authenticated user) should be able to submit an appeal request. This is outside the scope of requirements at this point.

### Rate Limiting

- **Purpose:** rate limiting on submission endpoint to keep realistic usage smooth while preventing abuse
- **Endpoints**: `POST /submit`
- **Decisions**:
	- requests over the limit get HTTP `429` (Too Many Requests)
	- limit: `10 per minute; 100 per day` per IP
	- local dev uses `storage_uri="memory://"`

### Audit Log

- **Purpose:** a structured record that captures timestamp, content ID, attribution result, confidence score, both individual signal scores, and whether an appeal has been filed.
- **Endpoints**: `GET /log`
- **Returns:** `{entries: [...]}` where each entry contains `creator_id, content_id, content_text, create_ts, llm_score, llm_reasoning, stylometric_score, attribution, confidence, status, creator_reasoning, appeal_ts`.
- **Design:** a SQLite  table keyed by `content_id`, where `/submit` inserts a row and`/appeal` updates it

## 5. Edge Cases & Known Limitations

- texts with heavy use of repetition and simple vocabulary which the stylometric heuristics might score as AI-generated
- texts originally generated by AI and then slightly polished by a human. This is likely to land in "uncertain" but could also be labeled "likely human" or "likely AI" depending on the text
- very short texts are difficult to get a stable stylometric score since there isn't much structure to work with
- AI is trained on human data, it is possible that sometimes people just write like AI (they could be too formal. Or their brains have been rewired because they read too many AI-generated texts. Yikes for humanity, you and me non-exclusive...)

## 6. AI Tool Plan

**M3 — submission endpoint + first signal**

- **Context to Provide**: the Architecture (Submission Flow and the diagram), Multi-Signal Detection (Signal 1), and Submission Endpoint (structure of the API endpoint) sections in this `planning.md` document
- **Prompt:** write the Flask app skeleton with the `POST /submit` endpoint and the LLM signal detection function according to the specs provided
- **Verify**: test with a few sample texts by calling the signal function directly before wiring into the endpoint, and confirm that the system returns a 0–1 score from the first signal 

**M4 — second signal + confidence scoring**

- **Context to Provide**: the Architecture (Submission Flow and the diagram), Multi-Signal Detection (Signal 2), and Confidence Scoring & Uncertainty sections of this `planning.md` document
- **Prompt:** write the stylometric signal detection function (returns 0–1) and the confidence scoring logic according to the specs provided
- **Verify**: test with a few sample texts that covers all three cases (clear AI, clear human, uncertain) and make sure that the system gives a reasonable combined score

**M5 — production layer**

- **Context to Provide**: the Architecture (both Flows and the diagram), Transparency Label, and Appeals Workflow sections in this `planning.md` document
- **Prompt:** write the label-mapping function and the `POST /appeal` endpoint according to specs provided
- **Verify:** test all three label variants are reachable and confirm that an appeal sets `under_review` and is logged with the original decision

## 7. Stretch Features (TBD)

<!-- 
### TO-DOs
- [ ] ensemble detection
- [ ] provenance certificate
- [ ] analytics dashboard
- [ ] multi-modal support
### Extra
- [ ] real calibrating function for confidence scoring with a labeled sample dataset
-->