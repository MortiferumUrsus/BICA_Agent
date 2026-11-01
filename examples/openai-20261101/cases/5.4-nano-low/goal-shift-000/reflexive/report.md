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
| Maximum working memory (reference tokens) | 126 |
| Maximum request incl. output reserve (reference tokens) | 5059 |
| Original input (reference tokens) | 2562 |
| Compressions | 5 |
| Retrieval rounds | 0 |
| Re-read text (reference tokens) | 0 |
| API calls / recorded attempts | 19 |
| HTTP / mock attempts | 19 |
| Provider prompt tokens | 14625 |
| Provider completion tokens | 3237 |
| Provider total tokens | 17862 |
| Total provider cost (USD) | 0.006971 |
| Known cost subtotal (USD) | 0.006971 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 29.384574 |
| API / transport errors | 0 |
| Invalid model output errors | 0 |

Wall time: 30.62 seconds.

### Usage by stage

| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer | 2 | 2 | 1041 | 124 | 0.000363 | 0.000363 | 1.715111 | 0 | 0 |
| assess | 5 | 5 | 5206 | 1316 | 0.002686 | 0.002686 | 10.493718 | 0 | 0 |
| compress | 5 | 5 | 5883 | 865 | 0.002258 | 0.002258 | 8.033562 | 0 | 0 |
| plan | 2 | 2 | 296 | 210 | 0.000322 | 0.000322 | 2.305125 | 0 | 0 |
| verify | 5 | 5 | 2199 | 722 | 0.001342 | 0.001342 | 6.837058 | 0 | 0 |

## Answers and failures

### goal-shift-000 · reflexive

Status: completed.

Question: Which supplier is cheapest among those delivering within 5 days? Return its name only.

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| answer: Vendor-00-A | answer: Vendor-00-A | [] |

Question: What is the contract code of the supplier with the shortest delivery time, regardless of price? Return only the exact code.

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| answer: Vendor-00-H | answer: Vendor-00-H | [] |


## Actual memory snapshot

Reason: transition. Stage: Read the provided goal and last_result to identify the target supplier and contract fields to recover..

| Before compression | After compression |
| --- | --- |
| [{"text": "Vendor-00-A: price=50; delivery_days=5 (eligible: delivery_days<=5).", "source_ids": ["c004"]}, {"text": "Vendor-00-H: price=82; delivery_days=1 (eligible: delivery_days<=5).", "source_ids": ["c001"]}, {"text": "Vendor-00-C: price=99; delivery_days=3 (eligible: delivery_days<=5).", "source_ids": ["c001"]}, {"text": "Vendor-00-I: price=236; delivery_days=2 (eligible: delivery_days<=5).", "source_ids": ["c001"]}] | [{"text": "Vendor-00-A: price=50; delivery_days=5 (eligible: delivery_days<=5).", "source_ids": ["c004"]}, {"text": "Vendor-00-H: price=82; delivery_days=1 (eligible: delivery_days<=5).", "source_ids": ["c001"]}, {"text": "Vendor-00-C: price=99; delivery_days=3 (eligible: delivery_days<=5).", "source_ids": ["c001"]}, {"text": "Vendor-00-I: price=236; delivery_days=2 (eligible: delivery_days<=5).", "source_ids": ["c001"]}] |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
