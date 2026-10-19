import json
import time


def evaluate(graph, cases_path):
    rows = []
    for case in json.loads(cases_path.read_text(encoding="utf-8")):
        started = time.perf_counter()
        answer = graph.invoke({"question": case["question"]})["response"]
        expected = set(case.get("expected_source_ids", []))
        actual = {c.source_id for c in answer.citations}
        expected_status = case.get("expected_status")
        rows.append(
            {
                **case,
                "response": answer.model_dump(),
                "latency_seconds": round(time.perf_counter() - started, 3),
                "status_match": answer.status == expected_status if expected_status else None,
                "expected_source_recall": len(expected & actual) / len(expected)
                if expected
                else None,
                "has_citation_if_answered": bool(answer.citations)
                if answer.status == "answered"
                else None,
                "human_faithfulness": None,
                "human_relevance": None,
                "failure_notes": "",
            }
        )
    return {
        "cases": rows,
        "note": "Citation presence is not faithfulness. Review support manually; unset expected labels are unscored.",
    }
