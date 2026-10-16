# Context memory — demo

LOCAL MODEL (Ollama). API cost excludes local compute.

Model: `llama3.2:1b`. Provider: `ollama`.

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
| retrieve: 2-5 distinctive words; IDs: ['c001', 'c002'] | insufficient_data:  | ["c001", "c002"] |

| Metric | Value |
| --- | ---: |
| Maximum working memory (reference tokens) | 45 |
| Maximum request incl. output reserve (reference tokens) | 1218 |
| Original input (reference tokens) | 62 |
| Compressions | 6 |
| Retrieval rounds | 1 |
| Re-read text (reference tokens) | 29 |
| API calls / recorded attempts | 9 |
| HTTP / mock attempts | 9 |
| Provider prompt tokens | 2005 |
| Provider completion tokens | 342 |
| Provider total tokens | 2347 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 22.069702 |
| API / transport errors | 0 |
| Invalid model output errors | 0 |

### correction · reflexive

Status: completed.

Question: What is the current delivery date for Orion?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| retrieve: 2-5 distinctive words; IDs: ['c002', 'c003'] | insufficient_data:  | ["c002", "c003"] |

| Metric | Value |
| --- | ---: |
| Maximum working memory (reference tokens) | 70 |
| Maximum request incl. output reserve (reference tokens) | 1364 |
| Original input (reference tokens) | 62 |
| Compressions | 6 |
| Retrieval rounds | 1 |
| Re-read text (reference tokens) | 36 |
| API calls / recorded attempts | 21 |
| HTTP / mock attempts | 21 |
| Provider prompt tokens | 6235 |
| Provider completion tokens | 1504 |
| Provider total tokens | 7739 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 89.805268 |
| API / transport errors | 0 |
| Invalid model output errors | 0 |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
