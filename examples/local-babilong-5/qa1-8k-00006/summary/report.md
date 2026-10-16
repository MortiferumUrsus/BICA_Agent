# Context memory — benchmark

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
  "max_api_calls": 500
}
```

## Measured totals

| Metric | Value |
| --- | ---: |
| Maximum working memory (reference tokens) | 30 |
| Maximum request incl. output reserve (reference tokens) | 2313 |
| Original input (reference tokens) | 7455 |
| Compressions | 9 |
| Retrieval rounds | 1 |
| Re-read text (reference tokens) | 1024 |
| API calls / recorded attempts | 12 |
| HTTP / mock attempts | 12 |
| Provider prompt tokens | 11059 |
| Provider completion tokens | 382 |
| Provider total tokens | 11441 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 31.994134 |
| API / transport errors | 0 |
| Invalid model output errors | 0 |

Wall time: 32.198 seconds.

### Usage by stage

| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer | 2 | 2 | 532 | 56 | 0 | 0 | 4.245447 | 0 | 0 |
| plan | 1 | 1 | 118 | 39 | 0 | 0 | 2.955667 | 0 | 0 |
| summary | 9 | 9 | 10409 | 287 | 0 | 0 | 24.793019 | 0 | 0 |

## Answers and failures

### qa1-8k-00006 · summary

Status: completed. Exact match: False.

Question: Where is Sandra?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| retrieve: 2-5 distinctive words; IDs: ['c001', 'c001'] | insufficient_data:  | ["c001"] |


## Actual memory snapshot

Reason: read. Stage: Read the current goal to understand what needs to be done..

| Before compression | After compression |
| --- | --- |
| [{"text": "Sandra", "source_ids": ["c001"]}, {"text": "Sandra travelled to the kitchen.", "source_ids": ["c001"]}] | [{"text": "Sandra", "source_ids": ["c001"]}, {"text": "Sandra travelled to Westminster.", "source_ids": ["c001"]}] |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
