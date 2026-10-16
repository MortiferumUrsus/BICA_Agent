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

Wall time: 8.648 seconds.

### Usage by stage

| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| assess | 1 | 1 | 1302 | 143 | 0 | 0 | 6.732554 | 0 | 1 |
| plan | 1 | 1 | 118 | 38 | 0 | 0 | 1.887805 | 0 | 0 |

## Answers and failures

### qa1-8k-00009 · reflexive

Status: error. Exact match: unknown.

Recorded error: {"type": "ResponseError", "message": "Model answer does not match the required JSON schema"}

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
