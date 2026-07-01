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



## 7. Spec Reflection

**One way the spec helped:** Writing the exact structure for audit log, as well as the input/output for the endpoints in `planning.md` was very helpful for implementation. When using AI for implementation, it was able to write code following the exact structure. This is also shown in the comments created by AI, all the fields are pretty much the same as the planning.md descriptions.

**One divergence and why:** AI didn't follow the exact order of the fields/columns of how I wanted the endpoints (both the submit and log) to output, even though the right order is set up for the audit log. I pointed AI to the structure of the audit log and told it to follow the exact order. It was initially ordering the fields by ascending alphabetical order of the field names. It was not necessarily a logic error, but it is a lot easier for human to debug when reviewing the output.

## 8. Documentation

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

**1. Same test from M3**
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

**2. Clearly AI-generated (should score high)**
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
  
**3. Clearly human-written (should score low)**
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

**4. Borderline: formal human writing (may score mid-high on stylometrics)**
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

**5. Borderline: lightly edited AI output (should ideally score mid-range)**
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

### M5: Production Layer

**Appeal Workflow**
```
curl -s -X POST http://localhost:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{"content_id": "28b459eb-2ebe-4a14-a412-e4d1033f9494", "creator_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical."}' | python -m json.tool
```

Output:
```
{
    "content_id": "28b459eb-2ebe-4a14-a412-e4d1033f9494",
    "status": "under_review",
    "message": "Your appeal has been submitted and is under review."
}
```

**Rate Limiting**
```
for i in $(seq 1 12); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:5000/submit \
	-H "Content-Type: application/json" \
	-d '{"text": "This is a test submission for rate limit testing purposes only.", "creator_id": "ratelimit-test"}'
done
```

Output:
```
200
200
200
200
200
200
200
200
200
200
429
429
```

**Complete Audit Log**

Rerun the 5 tests from M4 and the Appeal test above (note the audit log returns by most recent, so the first listed is the last test):
```
{
    "entries": [
        {
            "content_id": "21c5d0b4-aa72-4da2-8931-cac648cf9cd4",
            "creator_id": "tester",
            "content_text": "I've been thinking a lot about remote work lately. There are genuine tradeoffs \u2014 flexibility and no commute on one side, isolation and blurred work-life boundaries on the other. Studies show productivityvaries widely by individual and role type.",
            "create_ts": "2026-07-01T04:45:08.489488+00:00",
            "llm_score": 0.7,
            "llm_reasoning": "The text's balanced view and formal vocabulary suggest AI influence.",
            "stylometric_score": 0.5,
            "attribution": "uncertain",
            "confidence": 0.62,
            "status": "under_review",
            "creator_reasoning": "I wrote this myself from personal experience. I am a non-native English speaker and my writing style may appear more formal than typical.",
            "appeal_ts": "2026-07-01T04:46:36.955989+00:00"
        },
        {
            "content_id": "0dfa7f08-9e14-499d-91fa-4ffdb81f063b",
            "creator_id": "tester",
            "content_text": "The relationship between monetary policy and asset price inflation has been extensively studied in the literature. Central banks face a fundamental tension between their mandate for price stability and the unintended consequences of prolonged low interest rates on equity and real estate valuations.",
            "create_ts": "2026-07-01T04:45:08.257173+00:00",
            "llm_score": 0.8,
            "llm_reasoning": "The text uses overly formal vocabulary and maintains a tightly focused, balanced discussion.",
            "stylometric_score": 0.51592684897186,
            "attribution": "uncertain",
            "confidence": 0.686370739588744,
            "status": "classified",
            "creator_reasoning": null,
            "appeal_ts": null
        },
        {
            "content_id": "66f8b3f4-a886-4573-9ce8-0af3b89e6add",
            "creator_id": "tester",
            "content_text": "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. my friend got the spicyversion and said it was better. probably won't go back unless someone drags me there",
            "create_ts": "2026-07-01T04:45:07.857138+00:00",
            "llm_score": 0.1,
            "llm_reasoning": "The text contains informal language, personal opinions, and specific details, indicatinga human writer.",
            "stylometric_score": 0.3314400938439475,
            "attribution": "likely_human",
            "confidence": 0.19257603753757901,
            "status": "classified",
            "creator_reasoning": null,
            "appeal_ts": null
        },
        {
            "content_id": "57ce93b0-690b-4609-b497-ca7c78f06e8d",
            "creator_id": "tester",
            "content_text": "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment.",
            "create_ts": "2026-07-01T04:45:07.449132+00:00",
            "llm_score": 0.9,
            "llm_reasoning": "The text's formal vocabulary and balanced perspective suggest AI authorship.",
            "stylometric_score": 0.47311061671087035,
            "attribution": "likely_ai",
            "confidence": 0.7292442466843482,
            "status": "classified",
            "creator_reasoning": null,
            "appeal_ts": null
        },
        {
            "content_id": "5999cdc2-df33-40d7-be58-8dd25fc0b14e",
            "creator_id": "test-user-1",
            "content_text": "The sun dipped below the horizon, painting the sky in hues of amber and rose. I sat on the porch, coffee in hand, watching the neighborhood slowly go quiet.",
            "create_ts": "2026-07-01T04:40:47.914118+00:00",
            "llm_score": 0.2,
            "llm_reasoning": "The text's descriptive and personal tone suggests human authorship.",
            "stylometric_score": 0.5,
            "attribution": "likely_human",
            "confidence": 0.32,
            "status": "classified",
            "creator_reasoning": null,
            "appeal_ts": null
        }
    ]
}
```