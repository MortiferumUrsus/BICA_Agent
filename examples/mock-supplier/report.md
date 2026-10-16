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

### supplier · summary

Status: completed.

Question: Choose the cheapest supplier delivering within 5 days. Return its name only.

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| answer: Cedar | answer: Cedar | [] |

Question: What payment terms and contract code should the order use for the chosen supplier?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| answer: Cedar: payment 30% advance, contract CD-104 | answer: Cedar: payment 30% advance, contract CD-104 | [] |

| Metric | Value |
| --- | ---: |
| Maximum working memory (reference tokens) | 99 |
| Maximum request incl. output reserve (reference tokens) | 1261 |
| Original input (reference tokens) | 79 |
| Compressions | 5 |
| Retrieval rounds | 0 |
| Re-read text (reference tokens) | 0 |
| API calls / recorded attempts | 9 |
| HTTP / mock attempts | 9 |
| Provider prompt tokens | 0 |
| Provider completion tokens | 0 |
| Provider total tokens | 0 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 0 |
| API / transport errors | 0 |
| Invalid model output errors | 0 |

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

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
