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
| API calls / recorded attempts | 97 |
| HTTP / mock attempts | 97 |
| Provider prompt tokens | 90473 |
| Provider completion tokens | 9892 |
| Provider total tokens | 100365 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 546.116969 |
| API / transport errors | 0 |
| Invalid model output errors | 5 |

### Usage by stage

| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer | 10 | 10 | 3392 | 231 | 0 | 0 | 15.612611 | 0 | 0 |
| assess | 15 | 15 | 19353 | 2985 | 0 | 0 | 162.361632 | 0 | 3 |
| compress | 12 | 12 | 16942 | 1387 | 0 | 0 | 78.13375 | 0 | 0 |
| plan | 10 | 10 | 1180 | 386 | 0 | 0 | 23.60399 | 0 | 0 |
| summary | 38 | 38 | 46025 | 3688 | 0 | 0 | 211.526983 | 0 | 1 |
| verify | 12 | 12 | 3581 | 1215 | 0 | 0 | 54.878004 | 0 | 1 |

## Comparison

| Mode | Requested | Processed | Correct | Wrong answers | Failed examples | API errors | Model output errors | Limit errors | Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| summary | 5 | 4 | 0 | 4 | 1 | 0 | 1 | 0 | 0 |
| reflexive | 5 | 1 | 0 | 1 | 4 | 0 | 4 | 0 | 0 |

| Mode | Max memory | Compressions | Retrievals | Re-read tokens | Calls | Tokens | Cost USD | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| summary | 252 | 37 | 4 | 5120 | 51 | 53475 | 0 | 237.968211 |
| reflexive | 275 | 11 | 1 | 2048 | 46 | 46890 | 0 | 308.148759 |

Accuracy is exact match divided by all requested examples, including failed runs in the denominator. Wrong answers, API failures, invalid model output and limit failures are listed separately; processed counts include only completed examples. Empty and insufficient_data answers are wrong.

## Answers and failures

### qa1-8k-00005 · summary

Status: completed. Exact match: False.

Question: Where is Sandra?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| retrieve: ; IDs: ['c001'] | insufficient_data:  | ["c001"] |

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

### qa1-8k-00005 · reflexive

Status: error. Exact match: unknown.

Recorded error: {"type": "ResponseError", "message": "Model answer does not match the required JSON schema"}

| Metric | Value |
| --- | ---: |
| Maximum working memory (reference tokens) | 0 |
| Maximum request incl. output reserve (reference tokens) | 2348 |
| Original input (reference tokens) | 1024 |
| Compressions | 0 |
| Retrieval rounds | 0 |
| Re-read text (reference tokens) | 0 |
| API calls / recorded attempts | 2 |
| HTTP / mock attempts | 2 |
| Provider prompt tokens | 1414 |
| Provider completion tokens | 664 |
| Provider total tokens | 2078 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 37.575118 |
| API / transport errors | 0 |
| Invalid model output errors | 1 |

### qa1-8k-00006 · summary

Status: completed. Exact match: False.

Question: Where is Sandra?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| retrieve: 2-5 distinctive words; IDs: ['c001', 'c001'] | insufficient_data:  | ["c001"] |

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

### qa1-8k-00006 · reflexive

Status: error. Exact match: unknown.

Recorded error: {"type": "ResponseError", "message": "Model answer does not match the required JSON schema"}

| Metric | Value |
| --- | ---: |
| Maximum working memory (reference tokens) | 0 |
| Maximum request incl. output reserve (reference tokens) | 2433 |
| Original input (reference tokens) | 1024 |
| Compressions | 0 |
| Retrieval rounds | 0 |
| Re-read text (reference tokens) | 0 |
| API calls / recorded attempts | 2 |
| HTTP / mock attempts | 2 |
| Provider prompt tokens | 1457 |
| Provider completion tokens | 614 |
| Provider total tokens | 2071 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 33.393869 |
| API / transport errors | 0 |
| Invalid model output errors | 1 |

### qa1-8k-00007 · summary

Status: completed. Exact match: False.

Question: Where is Daniel?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| retrieve: 2-5 distinctive words; IDs: ['c003'] | insufficient_data:  | ["c003"] |

| Metric | Value |
| --- | ---: |
| Maximum working memory (reference tokens) | 252 |
| Maximum request incl. output reserve (reference tokens) | 2451 |
| Original input (reference tokens) | 7485 |
| Compressions | 9 |
| Retrieval rounds | 1 |
| Re-read text (reference tokens) | 1024 |
| API calls / recorded attempts | 12 |
| HTTP / mock attempts | 12 |
| Provider prompt tokens | 12956 |
| Provider completion tokens | 2189 |
| Provider total tokens | 15145 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 116.823153 |
| API / transport errors | 0 |
| Invalid model output errors | 0 |

### qa1-8k-00007 · reflexive

Status: error. Exact match: unknown.

Recorded error: {"type": "ResponseError", "message": "Model answer does not match the required JSON schema"}

| Metric | Value |
| --- | ---: |
| Maximum working memory (reference tokens) | 275 |
| Maximum request incl. output reserve (reference tokens) | 2765 |
| Original input (reference tokens) | 2048 |
| Compressions | 1 |
| Retrieval rounds | 0 |
| Re-read text (reference tokens) | 0 |
| API calls / recorded attempts | 7 |
| HTTP / mock attempts | 7 |
| Provider prompt tokens | 7412 |
| Provider completion tokens | 1521 |
| Provider total tokens | 8933 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 81.728513 |
| API / transport errors | 0 |
| Invalid model output errors | 1 |

### qa1-8k-00008 · summary

Status: completed. Exact match: False.

Question: Where is Sandra?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| retrieve: 2-5 distinctive words; IDs: ['c004', 'c006'] | insufficient_data:  | ["c004", "c006"] |

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

### qa1-8k-00008 · reflexive

Status: completed. Exact match: False.

Question: Where is Sandra?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| retrieve: ; IDs: ['c002', 'c001'] | insufficient_data:  | ["c002", "c001"] |

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

### qa1-8k-00009 · summary

Status: error. Exact match: unknown.

Recorded error: {"type": "ResponseError", "message": "Model answer does not match the required JSON schema"}

| Metric | Value |
| --- | ---: |
| Maximum working memory (reference tokens) | 0 |
| Maximum request incl. output reserve (reference tokens) | 2176 |
| Original input (reference tokens) | 1024 |
| Compressions | 0 |
| Retrieval rounds | 0 |
| Re-read text (reference tokens) | 0 |
| API calls / recorded attempts | 2 |
| HTTP / mock attempts | 2 |
| Provider prompt tokens | 1341 |
| Provider completion tokens | 60 |
| Provider total tokens | 1401 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 3.904477 |
| API / transport errors | 0 |
| Invalid model output errors | 1 |

### qa1-8k-00009 · reflexive

Status: error. Exact match: unknown.

Recorded error: {"type": "ResponseError", "message": "Model answer does not match the required JSON schema"}

| Metric | Value |
| --- | ---: |
| Maximum working memory (reference tokens) | 0 |
| Maximum request incl. output reserve (reference tokens) | 2329 |
| Original input (reference tokens) | 1024 |
| Compressions | 0 |
| Retrieval rounds | 0 |
| Re-read text (reference tokens) | 0 |
| API calls / recorded attempts | 2 |
| HTTP / mock attempts | 2 |
| Provider prompt tokens | 1420 |
| Provider completion tokens | 181 |
| Provider total tokens | 1601 |
| Total provider cost (USD) | 0 |
| Known cost subtotal (USD) | 0 |
| Calls with unknown cost | 0 |
| Sum of request duration (seconds) | 8.620359 |
| API / transport errors | 0 |
| Invalid model output errors | 1 |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
