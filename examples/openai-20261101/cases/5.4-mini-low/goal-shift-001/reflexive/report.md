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
| Maximum working memory (reference tokens) | 111 |
| Maximum request incl. output reserve (reference tokens) | 5018 |
| Original input (reference tokens) | 2562 |
| Compressions | 5 |
| Retrieval rounds | 0 |
| Re-read text (reference tokens) | 0 |
| API calls / recorded attempts | 19 |
| HTTP / mock attempts | 19 |
| Provider prompt tokens | 13743 |
| Provider completion tokens | 2813 |
| Provider total tokens | 16556 |
| Total provider cost (USD) | 0.022966 |
| Known cost subtotal (USD) | 0.022966 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 21.75386 |
| API / transport errors | 0 |
| Invalid model output errors | 0 |

Wall time: 23.124 seconds.

### Usage by stage

| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer | 2 | 2 | 861 | 120 | 0.001186 | 0.001186 | 1.623078 | 0 | 0 |
| assess | 5 | 5 | 4991 | 1133 | 0.008842 | 0.008842 | 7.12351 | 0 | 0 |
| compress | 5 | 5 | 5508 | 707 | 0.007313 | 0.007313 | 5.285854 | 0 | 0 |
| plan | 2 | 2 | 296 | 202 | 0.001131 | 0.001131 | 2.050444 | 0 | 0 |
| verify | 5 | 5 | 2087 | 651 | 0.004495 | 0.004495 | 5.670973 | 0 | 0 |

## Answers and failures

### goal-shift-001 · reflexive

Status: completed.

Question: Which supplier is cheapest among those delivering within 5 days? Return its name only.

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| answer: Vendor-01-D | answer: Vendor-01-D | [] |

Question: What is the contract code of the supplier with the shortest delivery time, regardless of price? Return only the exact code.

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| answer: AG-88779-1 | answer: AG-88779-1 | [] |


## Actual memory snapshot

Reason: transition. Stage: Keep last_result vendor code in memory..

| Before compression | After compression |
| --- | --- |
| [{"text": "Vendor-01-B has price=154 and delivery_days=4; contract_code=AG-88779-1; payment=on delivery.", "source_ids": ["c001"]}, {"text": "Vendor-01-D has price=50 and delivery_days=5; contract_code=AG-68601-3; payment=on delivery.", "source_ids": ["c004"]}, {"text": "Vendor-01-D has the lower price among the suppliers with delivery_days <= 5.", "source_ids": ["c004"]}] | [{"text": "Vendor-01-B has delivery_days=4 and contract_code=AG-88779-1.", "source_ids": ["c001"]}, {"text": "Vendor-01-D has delivery_days=5 and contract_code=AG-68601-3.", "source_ids": ["c004"]}] |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
