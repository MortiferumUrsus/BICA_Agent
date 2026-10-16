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

Wall time: 117.026 seconds.

### Usage by stage

| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| answer | 2 | 2 | 970 | 47 | 0 | 0 | 3.264812 | 0 | 0 |
| plan | 1 | 1 | 118 | 38 | 0 | 0 | 3.64167 | 0 | 0 |
| summary | 9 | 9 | 11868 | 2104 | 0 | 0 | 109.916671 | 0 | 0 |

## Answers and failures

### qa1-8k-00007 · summary

Status: completed. Exact match: False.

Question: Where is Daniel?

| Decision before retrieval | Final decision | Retrieved chunk IDs |
| --- | --- | --- |
| retrieve: 2-5 distinctive words; IDs: ['c003'] | insufficient_data:  | ["c003"] |


## Actual memory snapshot

Reason: read. Stage: Read the current goal to understand what needs to be done..

| Before compression | After compression |
| --- | --- |
| [{"text": "Simon of Montfort", "source_ids": ["c001"]}] | [{"text": "Daniel", "source_ids": ["c002"]}, {"text": "Norman descent within a generation or two after the Conquest", "source_ids": ["c001", "c002"]}, {"text": "English lands according to English law; equal terms with other landowners of English birth", "source_ids": ["c001"]}, {"text": "French varnish,", "source_ids": ["c001"]}, {"text": "Normans, in their sojourn in Gaul, had put on a slight French varnish,", "source_ids": ["c001"]}, {"text": "Yorkshire or Lincolnshire who has somehow picked up a bad habit of talking French", "source_ids": ["c002"]}, {"text": "Contemporary writers; incidental notices that, among all classes between the highest and the lowest,\namong all between the great noble and the villain, the distinction of Norman and Englishman had been forgotten within little more than a\nhundred years after the time when King William came into England", "source_ids": ["c001", "c002"]}, {"text": "Henry the Second, Count of Anjou through his father, Duke of Aquitaine\nthrough his wife, inherited also his mother’s claims on Normandy and England,", "source_ids": ["c001", "c002"]}] |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
