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
| Maximum working memory (reference tokens) | 225 |
| Maximum request incl. output reserve (reference tokens) | 2430 |
| Original input (reference tokens) | 7416 |
| Compressions | 10 |
| Retrieval rounds | 1 |
| Re-read text (reference tokens) | 2048 |
| API calls / recorded attempts | 13 |
| HTTP / mock attempts | 13 |
| Provider prompt tokens | 12902 |
| Provider completion tokens | 1032 |
| Provider total tokens | 13934 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 54.665189 |
| API / transport errors | 0 |
| Invalid model output errors | 0 |

Wall time: 54.858 seconds.

### Usage by stage

| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer | 2 | 2 | 707 | 53 | 0 | 0 | 2.916024 | 0 | 0 |
| plan | 1 | 1 | 118 | 39 | 0 | 0 | 1.932793 | 0 | 0 |
| summary | 10 | 10 | 12077 | 940 | 0 | 0 | 49.816372 | 0 | 0 |

## Answers and failures

### qa1-8k-00008 · summary

Status: completed. Exact match: False.

Question: Where is Sandra?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| retrieve: 2-5 distinctive words; IDs: ['c004', 'c006'] | insufficient_data:  | ["c004", "c006"] |


## Actual memory snapshot

Reason: read. Stage: Read the current goal to understand what needs to be done..

| Before compression | After compression |
| --- | --- |
| [{"text": "Sandra", "source_ids": ["c001"]}, {"text": "Suza Fairfield", "source_ids": ["c001"]}, {"text": "Aunt Katy", "source_ids": ["c001"]}, {"text": "Port William", "source_ids": ["c001"]}, {"text": "Canada", "source_ids": ["c001"]}, {"text": "Queen s Dominion", "source_ids": ["c001"]}, {"text": "Demitt estate", "source_ids": ["c001"]}, {"text": "Aunt Katy's money", "source_ids": ["c001"]}] | [{"text": "Suza Fairfield escaped from Tom Ditamus' caravan by following the Kentucky river.", "source_ids": ["c002"]}] |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
