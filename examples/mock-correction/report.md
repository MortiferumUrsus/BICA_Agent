# Context memory — demo

MOCK: scripted responses.

Model: `deterministic-demo-fixture`. Provider: `mock`.

Presentation: `not specified`. Reference tokens measure application limits; provider usage measures actual model requests.

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

## Answers and failures

### correction · summary

Status: completed.

Question: What is the current delivery date for Orion?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| answer: 19 November 2026 | answer: 19 November 2026 | [] |

| Metric | Value |
| --- | ---: |
| Maximum working memory (reference tokens) | 30 |
| Maximum request incl. output reserve (reference tokens) | 1150 |
| Original input (reference tokens) | 62 |
| Compressions | 4 |
| Retrieval rounds | 0 |
| Re-read text (reference tokens) | 0 |
| API calls / recorded attempts | 6 |
| HTTP / mock attempts | 6 |
| Provider prompt tokens | 0 |
| Provider completion tokens | 0 |
| Provider total tokens | 0 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 0 |
| API / transport errors | 0 |
| Invalid model output errors | 0 |

### correction · reflexive

Status: completed.

Question: What is the current delivery date for Orion?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| answer: 19 November 2026 | answer: 19 November 2026 | [] |

| Metric | Value |
| --- | ---: |
| Maximum working memory (reference tokens) | 30 |
| Maximum request incl. output reserve (reference tokens) | 1257 |
| Original input (reference tokens) | 62 |
| Compressions | 4 |
| Retrieval rounds | 0 |
| Re-read text (reference tokens) | 0 |
| API calls / recorded attempts | 14 |
| HTTP / mock attempts | 14 |
| Provider prompt tokens | 0 |
| Provider completion tokens | 0 |
| Provider total tokens | 0 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 0 |
| API / transport errors | 0 |
| Invalid model output errors | 0 |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
