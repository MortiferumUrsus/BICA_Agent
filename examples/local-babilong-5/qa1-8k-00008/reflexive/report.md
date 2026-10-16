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
| Maximum working memory (reference tokens) | 67 |
| Maximum request incl. output reserve (reference tokens) | 2510 |
| Original input (reference tokens) | 7416 |
| Compressions | 10 |
| Retrieval rounds | 1 |
| Re-read text (reference tokens) | 2048 |
| API calls / recorded attempts | 33 |
| HTTP / mock attempts | 33 |
| Provider prompt tokens | 29368 |
| Provider completion tokens | 2839 |
| Provider total tokens | 32207 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 146.8309 |
| API / transport errors | 0 |
| Invalid model output errors | 0 |

Wall time: 147.234 seconds.

### Usage by stage

| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer | 2 | 2 | 605 | 39 | 0 | 0 | 1.941297 | 0 | 0 |
| assess | 10 | 10 | 12596 | 1051 | 0 | 0 | 56.72454 | 0 | 0 |
| compress | 10 | 10 | 13569 | 945 | 0 | 0 | 53.388357 | 0 | 0 |
| plan | 1 | 1 | 118 | 39 | 0 | 0 | 1.815704 | 0 | 0 |
| verify | 10 | 10 | 2480 | 765 | 0 | 0 | 32.961001 | 0 | 0 |

## Answers and failures

### qa1-8k-00008 · reflexive

Status: completed. Exact match: False.

Question: Where is Sandra?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| retrieve: ; IDs: ['c002', 'c001'] | insufficient_data:  | ["c002", "c001"] |


## Actual memory snapshot

Reason: read. Stage: Read the current goal to understand what needs to be done..

| Before compression | After compression |
| --- | --- |
| [{"text": "Sandra went to the kitchen.", "source_ids": ["c001"]}, {"text": "Aunt Katy had money of her own, earned with her own hands.", "source_ids": ["c001"]}] | [{"text": "Sandra Fairfield.", "source_ids": ["c002"]}, {"text": "Aunt Katy.", "source_ids": ["c001"]}, {"text": "Suza Fairfield left Tom Ditamus and his family sleeping soundly on the bank of the creek in the dark woods.", "source_ids": ["c002", "c001"]}] |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
