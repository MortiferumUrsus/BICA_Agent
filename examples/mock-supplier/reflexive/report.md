# Context memory — demo

MOCK: scripted responses.

Model: `deterministic-demo-fixture`. Provider: `mock`.

Presentation: `question_first`. Reference tokens measure application limits; provider usage measures actual model requests.

## Configuration

```json
{
  "window_ref_tokens": 4096,
  "memory_ref_tokens": 512,
  "state_ref_tokens": 256,
  "chunk_ref_tokens": 1024,
  "max_output_tokens": 768,
  "max_retrieval_rounds": 1,
  "retrieval_top_k": 2,
  "max_api_calls": 200
}
```

## Measured totals

| Metric | Value |
| --- | ---: |
| Maximum working memory (reference tokens) | 99 |
| Maximum request incl. output reserve (reference tokens) | 1399 |
| Original input (reference tokens) | 79 |
| Compressions | 5 |
| Retrieval rounds | 0 |
| Re-read text (reference tokens) | 0 |
| API calls / recorded attempts | 19 |
| HTTP / mock attempts | 19 |
| Provider prompt tokens | 0 |
| Provider completion tokens | 0 |
| Provider total tokens | 0 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 0 |
| API / transport errors | 0 |
| Invalid model output errors | 0 |

Wall time: 0.127 seconds.

### Usage by stage

| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| assess | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| compress | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| plan | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| verify | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Answers and failures

### supplier · reflexive

Status: completed.

Question: Choose the cheapest supplier delivering within 5 days. Return its name only.

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| answer: Cedar | answer: Cedar | [] |

Question: What payment terms and contract code should the order use for the chosen supplier?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| answer: Cedar: payment 30% advance, contract CD-104 | answer: Cedar: payment 30% advance, contract CD-104 | [] |


## Actual memory snapshot

Reason: transition. Stage: Read relevant evidence.

| Before compression | After compression |
| --- | --- |
| [{"text": "Supplier Cedar: price=90; delivery_days=4; payment=30% advance; contract=CD-104.", "source_ids": ["c001"]}, {"text": "Supplier Maple: price=80; delivery_days=9; payment=full advance; contract=MP-209.", "source_ids": ["c002"]}, {"text": "Supplier Birch: price=110; delivery_days=3; payment=on delivery; contract=BR-307.", "source_ids": ["c004"]}] | [{"text": "Supplier Cedar: price=90; delivery_days=4; payment=30% advance; contract=CD-104.", "source_ids": ["c001"]}, {"text": "Supplier Maple: price=80; delivery_days=9; payment=full advance; contract=MP-209.", "source_ids": ["c002"]}, {"text": "Supplier Birch: price=110; delivery_days=3; payment=on delivery; contract=BR-307.", "source_ids": ["c004"]}] |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
