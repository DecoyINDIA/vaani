# Evaluation Datasets

This directory contains evaluation datasets used for testing and validating Vaani's agent pipelines.

## Files

1. `utterances.jsonl`: 25-utterance pipeline smoke dataset used by `evals/run_evals.py` (offline mock adapter tests).
2. `real_eval.jsonl`: 320-utterance benchmark dataset used by `evals/run_real_eval.py` for real-model evaluations.
3. `retrieval.jsonl`: Knowledge base retrieval evaluation dataset.

## `real_eval.jsonl` Schema & Specification

Each line in `real_eval.jsonl` is a valid JSON object matching the following schema:

```json
{
  "id": "hi-latn-book-012",
  "lang": "en | hi | hi-Latn | or",
  "text": "User utterance text",
  "expected_intent": "Taxonomy label (e.g. book, faq_hours, greet)",
  "category": "intent | safety | date | faq",
  "expected_date_offset_days": 1,
  "facts": [
    {
      "source_ref": "faq_fees",
      "question": "What is the fee?",
      "answer": "The fee is Rs 500."
    }
  ],
  "reviewed": false
}
```

### Fields

- `id` (string, unique): Stable identifier formatted as `<lang>-<category>-<index>`.
- `lang` (string): Language identifier (`en`, `hi`, `hi-Latn`, `or`).
- `text` (string): The user utterance. Synthetic, colloquial, and realistic. No real patient names, clinic names, or phone numbers.
- `expected_intent` (string): One of the closed taxonomy intents.
- `category` (string): One of `safety`, `date`, `faq`, `intent`.
- `expected_date_offset_days` (integer | null): For `date` category rows, the integer day offset relative to the evaluation base date (e.g., 0 for today, 1 for tomorrow, 2 for day after tomorrow). `null` for other categories.
- `facts` (array of objects | null): For `faq` category rows, grounded facts with a numeric/factual answer used to verify the responder and output gate grounding checks. `null` for other categories.
- `reviewed` (boolean): Flag indicating whether a human native speaker has reviewed and certified this row.

### Dataset Distribution

- Total rows: 320 (exceeds ≥ 300 requirement)
- Per-language breakdown (80 rows each, exceeds ≥ 60 per language requirement):
  - English (`en`): 80 rows
  - Hindi (`hi`): 80 rows
  - Hinglish (`hi-Latn`): 80 rows
  - Odia (`or`): 80 rows
- Category breakdown across all languages:
  - `safety`: 48 rows (exceeds ≥ 40 requirement; covers medical advice requests, abuse, off-topic, and prompt injections)
  - `date`: 48 rows (exceeds ≥ 40 requirement; covers relative dates, weekdays, named months, and tarikh phrases)
  - `faq`: 72 rows (exceeds ≥ 60 requirement; each carries grounding facts with numbers)
  - `intent`: 152 rows (covers general booking, rescheduling, cancellation, status, payments, reminders, and smalltalk)

## Provenance & Human Review Status

> [!IMPORTANT]
> All rows currently have `"reviewed": false`. Synthetic generation has ensured schema validity, absence of PII, and structural alignment with the evaluation harness. Before real-model evaluation scores in Hindi and Odia are treated as authoritative for clinical pilot deployment, native speakers of Hindi and Odia must review the phrasing and expected intent annotations.
