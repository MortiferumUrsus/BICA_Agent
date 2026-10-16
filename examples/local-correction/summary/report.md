# Context memory — demo

LOCAL MODEL (Ollama). API cost excludes local compute.

Model: `llama3.2:1b`. Provider: `ollama`.

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

Wall time: 22.62 seconds.

### Usage by stage

| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer | 2 | 2 | 610 | 56 | 0 | 0 | 3.370302 | 0 | 0 |
| plan | 1 | 1 | 122 | 53 | 0 | 0 | 3.067484 | 0 | 0 |
| summary | 6 | 6 | 1273 | 233 | 0 | 0 | 15.631917 | 0 | 0 |

## Answers and failures

### correction · summary

Status: completed.

Question: What is the current delivery date for Orion?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| retrieve: 2-5 distinctive words; IDs: ['c001', 'c002'] | insufficient_data:  | ["c001", "c002"] |


## Actual memory snapshot

Reason: read. Stage: Read the current delivery date from the local source journal.

| Before compression | After compression |
| --- | --- |
| [{"text": "The current delivery date for Orion is 12 November 2026.", "source_ids": ["c001"]}] | [{"text": "Orion's current delivery date is 12 November 2026.", "source_ids": ["c001", "c002"]}] |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
