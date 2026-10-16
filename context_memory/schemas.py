from copy import deepcopy


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def string(max_length=240):
    return {"type": "string", "maxLength": max_length}


def array(items, maximum=8):
    return {"type": "array", "items": items, "maxItems": maximum}


FACT = obj({"text": {"type": "string", "minLength": 1, "maxLength": 500},
            "source_ids": {"type": "array", "items": {"type": "string", "pattern": "^c[0-9]+$"}, "minItems": 1, "maxItems": 6, "uniqueItems": True}})
MEMORY = array(FACT, 8)
SCHEMAS = {
    "plan": obj({"plan": {"type": "array", "items": string(120), "minItems": 1, "maxItems": 4}}),
    "summary": obj({"memory": MEMORY}),
    "assess": obj({"current_stage": string(100), "remaining_steps": array(string(100), 4),
                   "missing_data": array(string(120), 4), "selected_facts": MEMORY}),
    "compress": obj({"memory": MEMORY}),
    "verify": obj({"issues": array(string(160), 6), "memory": MEMORY}),
    "answer": obj({"status": {"type": "string", "enum": ["answer", "retrieve", "insufficient_data"]},
                   "answer": string(400), "query": string(160), "source_ids": array(string(32), 6)}),
}


def schema_for(stage):
    return deepcopy(SCHEMAS[stage])
