# Context memory — benchmark

Provider: openai-api.

Model: `gpt-5.4-nano-2026-03-17`. Provider: `openai-api`.

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
| Maximum working memory (reference tokens) | 188 |
| Maximum request incl. output reserve (reference tokens) | 4683 |
| Original input (reference tokens) | 2562 |
| Compressions | 7 |
| Retrieval rounds | 1 |
| Re-read text (reference tokens) | 312 |
| API calls / recorded attempts | 12 |
| HTTP / mock attempts | 12 |
| Provider prompt tokens | 7333 |
| Provider completion tokens | 2046 |
| Provider total tokens | 9379 |
| Total provider cost (USD) | 0.004024 |
| Known cost subtotal (USD) | 0.004024 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 19.040795 |
| API / transport errors | 0 |
| Invalid model output errors | 0 |

Wall time: 20.124 seconds.

### Usage by stage

| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer | 3 | 3 | 1591 | 238 | 0.000616 | 0.000616 | 3.19512 | 0 | 0 |
| plan | 2 | 2 | 296 | 201 | 0.00031 | 0.00031 | 2.17724 | 0 | 0 |
| summary | 7 | 7 | 5446 | 1607 | 0.003098 | 0.003098 | 13.668435 | 0 | 0 |

## Answers and failures

### goal-shift-000 · summary

Status: completed.

Question: Which supplier is cheapest among those delivering within 5 days? Return its name only.

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| answer: Vendor-00-A | answer: Vendor-00-A | [] |

Question: What is the contract code of the supplier with the shortest delivery time, regardless of price? Return only the exact code.

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| retrieve: fastest supplier contract_code Vendor-00-A delivery time contract_code; IDs: [] | answer: AG-10894-7 | ["c001", "c004"] |


## Actual memory snapshot

Reason: transition. Stage: read text to identify the updated rule: prioritize fastest supplier over price..

| Before compression | After compression |
| --- | --- |
| [{"text": "Previously, the cheapest supplier delivering within 5 days was recorded as Vendor-00-H with price=82, delivery_days=1, contract_code=AG-10894-7, payment=on delivery (source c001).", "source_ids": ["c001"]}, {"text": "Archive meetings 82–89 indicated: \"No supplier decisions were made,\" so the cheapest supplier for the goal was not confirmed by c003.", "source_ids": ["c003"]}, {"text": "Confirmed correction: Vendor-00-A now has price=50; delivery times and contract codes are unchanged (so this supersedes the prior cheapest supplier record).", "source_ids": ["c004"]}] | [{"text": "Previously, the purchasing logic recorded the cheapest supplier (within 5 days): Vendor-00-H with price=82, delivery_days=1, contract_code=AG-10894-7, payment=on delivery (source c001).", "source_ids": ["c001"]}, {"text": "Archive meetings 82–89 indicated: \"No supplier decisions were made,\" so the cheapest supplier for the goal was not confirmed by c003.", "source_ids": ["c003"]}, {"text": "Confirmed correction: Vendor-00-A now has price=50; delivery times and contract codes are unchanged (so this supersedes the prior cheapest supplier record).", "source_ids": ["c004"]}, {"text": "Goal update: purchasing priority changed to choose the fastest supplier regardless of price and recover its contract_code; the fastest-supplier contract_code is not available in provided sources.", "source_ids": ["c001", "c003", "c004"]}] |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
