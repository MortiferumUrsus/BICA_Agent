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

Wall time: 81.82 seconds.

### Usage by stage

| Stage | Calls | Attempts | Prompt tokens | Completion tokens | Cost USD | Known cost USD | Seconds | API errors | Output errors |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| assess | 2 | 2 | 2820 | 591 | 0 | 0 | 33.156111 | 0 | 0 |
| compress | 2 | 2 | 3373 | 442 | 0 | 0 | 24.745393 | 0 | 0 |
| plan | 1 | 1 | 118 | 38 | 0 | 0 | 1.910006 | 0 | 0 |
| verify | 2 | 2 | 1101 | 450 | 0 | 0 | 21.917003 | 0 | 1 |

## Answers and failures

### qa1-8k-00007 · reflexive

Status: error. Exact match: unknown.

Recorded error: {"type": "ResponseError", "message": "Model answer does not match the required JSON schema"}


## Actual memory snapshot

Reason: read. Stage: Read the current goal to understand what needs to be done..

| Before compression | After compression |
| --- | --- |
| [] | [{"text": "But we need not speculate as to what might have been; it is\nenough that one man did arise to do the work, that there is one man to\nwhom we owe that the wonderful thirteenth century, the great creative\nand destructive age throughout the world(14), was to us an age of\ncreation and not of destruction. That man, the man who finally gave to\nEnglish freedom its second and more lasting shape, the hero and martyr\nof England in the greatest of her constitutional struggles, was Simon\nof Montfort, Earl of莱", "source_ids": ["c001"]}, {"text": "The land of his birth was—shall I say flourishing or suffering?—under the baleful\nvirtues of the most righteous of Kings. Saint Lewis reigned in France,\nSaint Lewis the just and holy, the man who never swerved from the path\nof right, the man who swared to his neighbour and disappointed him not,\nthough it were to his own hindrance.", "source_ids": ["c001"]}, {"text": "He thus did more than any other man to strengthen its power. He thus didmore than any other man to pave the way for that foul despotism ofhis successors whose evil deeds would have daily vexed his righteous soul.", "source_ids": ["c001"]}] |

## Files

Source chunks: journal.jsonl. State and memory: state.json, memory.json and memory_versions.jsonl. Execution trace: trace.jsonl. Requests, responses and usage: api_calls.jsonl.
