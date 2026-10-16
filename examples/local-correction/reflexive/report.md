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

Wall time: 90.021 seconds.

### Usage by stage

| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer | 2 | 2 | 631 | 53 | 0 | 0 | 3.585135 | 0 | 0 |
| assess | 6 | 6 | 1895 | 502 | 0 | 0 | 29.048604 | 0 | 0 |
| compress | 6 | 6 | 2339 | 374 | 0 | 0 | 22.526313 | 0 | 0 |
| plan | 1 | 1 | 122 | 53 | 0 | 0 | 3.204176 | 0 | 0 |
| verify | 6 | 6 | 1248 | 522 | 0 | 0 | 31.441039 | 0 | 0 |

## Answers and failures

### correction · reflexive

Status: completed.

Question: What is the current delivery date for Orion?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| retrieve: 2-5 distinctive words; IDs: ['c002', 'c003'] | insufficient_data:  | ["c002", "c003"] |


## Actual memory snapshot

Reason: read. Stage: Read the current delivery date from the local source journal.

| Before compression | After compression |
| --- | --- |
| [{"text": "What is the current delivery date for Orion?", "source_ids": ["c001"]}, {"text": "Orion delivery date: 12 November 2026.", "source_ids": ["c001"]}] | [{"text": "Orion delivery date: 12 November 2026.", "source_ids": ["c001"]}, {"text": "No delivery changes were made.", "source_ids": ["c002"]}] |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
