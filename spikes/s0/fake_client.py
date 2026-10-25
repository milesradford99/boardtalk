"""Offline stand-in for the Ark client, used with S0_FAKE=1 to dry-run the pipeline for free.

It answers the forced `emit` tool with schema-valid input built from the tool's input_schema.
"""


def _fill(schema: dict, hint: str):
    t = schema.get("type")
    if "enum" in schema:
        return schema["enum"][0]
    if t == "object":
        return {k: _fill(v, k) for k, v in schema.get("properties", {}).items()}
    if t == "array":
        n = 20 if hint == "questions" else 2
        return [_fill(schema["items"], hint) for _ in range(n)]
    if t == "integer":
        return -1 if hint == "supersedes" else 1
    if t == "boolean":
        return True
    return f"fake {hint}"


class FakeClient:
    def create(self, body: dict) -> dict:
        if "tools" not in body:
            tag = "digest" if "<digest>" in body["system"][0]["text"] else "summary"
            return {"stop_reason": "end_turn", "usage": {"input_tokens": 1000, "output_tokens": 500},
                    "content": [{"type": "text", "text": f"<{tag}>" + "fake text " * 40 + f"</{tag}>"}]}
        out = _fill(body["tools"][0]["input_schema"], "")
        if "questions" in out:  # make ids/categories/src_turn realistic enough for the downstream steps
            cats = ["identifier", "decision", "dead_end", "state"]
            for i, q in enumerate(out["questions"]):
                q.update(category=cats[i % 4], src_turn=0, exact="turn 0" if i % 4 == 0 else "")
        if "answers" in out:
            out["answers"] = [{"id": i, "answer": "turn 0"} for i in range(20)]
        chars = sum(len(b["text"]) for m in body["messages"] for b in m["content"])
        return {"stop_reason": "tool_use", "content": [{"type": "tool_use", "name": "emit", "input": out}],
                "usage": {"input_tokens": chars // 4, "output_tokens": 200}}
