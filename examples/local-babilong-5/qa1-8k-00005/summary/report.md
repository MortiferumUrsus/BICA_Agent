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
| Maximum working memory (reference tokens) | 59 |
| Maximum request incl. output reserve (reference tokens) | 2245 |
| Original input (reference tokens) | 7588 |
| Compressions | 9 |
| Retrieval rounds | 1 |
| Re-read text (reference tokens) | 1024 |
| API calls / recorded attempts | 12 |
| HTTP / mock attempts | 12 |
| Provider prompt tokens | 11144 |
| Provider completion tokens | 410 |
| Provider total tokens | 11554 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 30.581259 |
| API / transport errors | 0 |
| Invalid model output errors | 0 |

Wall time: 31.316 seconds.

### Usage by stage

| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer | 2 | 2 | 578 | 36 | 0 | 0 | 3.245031 | 0 | 0 |
| plan | 1 | 1 | 118 | 39 | 0 | 0 | 2.319153 | 0 | 0 |
| summary | 9 | 9 | 10448 | 335 | 0 | 0 | 25.017076 | 0 | 0 |

## Answers and failures

### qa1-8k-00005 · summary

Status: completed. Exact match: False.

Question: Where is Sandra?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| retrieve: ; IDs: ['c001'] | insufficient_data:  | ["c001"] |


## Actual memory snapshot

Reason: read. Stage: Read the current goal to understand what needs to be done..

| Before compression | After compression |
| --- | --- |
| [{"text": "Sandra", "source_ids": ["c001"]}, {"text": "Sandra is missing", "source_ids": ["c001"]}] | [{"text": "Sandra is missing", "source_ids": ["c001"]}, {"text": "Sandra is presumed dead", "source_ids": ["c001"]}] |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
