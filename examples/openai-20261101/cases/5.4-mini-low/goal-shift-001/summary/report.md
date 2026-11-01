# Context memory — benchmark

Provider: openai-api.

Model: `gpt-5.4-mini-2026-03-17`. Provider: `openai-api`.

Presentation: `question_first`. Reference tokens measure application limits; provider usage measures actual model requests.

## Configuration

```json
{
  "window_ref_tokens": 8192,
  "memory_ref_tokens": 512,
  "state_ref_tokens": 512,
  "chunk_ref_tokens": 2048,
  "max_output_tokens": 2048,
  "max_retrieval_rounds": 1,
  "retrieval_top_k": 2,
  "max_api_calls": 250,
  "format_retries": 2
}
```

## Measured totals

| Metric | Value |
| --- | ---: |
| Maximum working memory (reference tokens) | 106 |
| Maximum request incl. output reserve (reference tokens) | 4681 |
| Original input (reference tokens) | 2562 |
| Compressions | 5 |
| Retrieval rounds | 0 |
| Re-read text (reference tokens) | 0 |
| API calls / recorded attempts | 9 |
| HTTP / mock attempts | 9 |
| Provider prompt tokens | 5355 |
| Provider completion tokens | 976 |
| Provider total tokens | 6331 |
| Total provider cost (USD) | 0.008408 |
| Known cost subtotal (USD) | 0.008408 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 9.413613 |
| API / transport errors | 0 |
| Invalid model output errors | 0 |

Wall time: 10.501 seconds.

### Usage by stage

| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer | 2 | 2 | 876 | 96 | 0.001089 | 0.001089 | 1.64101 | 0 | 0 |
| plan | 2 | 2 | 296 | 203 | 0.001136 | 0.001136 | 2.391103 | 0 | 0 |
| summary | 5 | 5 | 4183 | 677 | 0.006184 | 0.006184 | 5.3815 | 0 | 0 |

## Answers and failures

### goal-shift-001 · summary

Status: completed.

Question: Which supplier is cheapest among those delivering within 5 days? Return its name only.

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| answer: Vendor-01-D | answer: Vendor-01-D | [] |

Question: What is the contract code of the supplier with the shortest delivery time, regardless of price? Return only the exact code.

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| answer: AG-68601-3 | answer: AG-68601-3 | [] |


## Actual memory snapshot

Reason: transition. Stage: Keep "Vendor-01-D" and the purchasing-priority change in memory..

| Before compression | After compression |
| --- | --- |
| [{"text": "Cheapest supplier delivering within 5 days: Vendor-01-D, price=50, delivery_days=5, contract_code=AG-68601-3, payment=on delivery. Previous price was 133; corrected by c004.", "source_ids": ["c001", "c004"]}] | [{"text": "Fastest supplier: Vendor-01-D, delivery_days=5, contract_code=AG-68601-3, payment=on delivery.", "source_ids": ["c001", "c004"]}, {"text": "Previous identification was cheapest supplier delivering within 5 days: Vendor-01-D, price=50, delivery_days=5, contract_code=AG-68601-3, payment=on delivery; previous price was 133, corrected by c004.", "source_ids": ["c001", "c004"]}] |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
