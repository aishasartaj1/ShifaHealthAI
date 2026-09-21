from src.trace import TraceRecorder, summarize_result


class FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


def test_summarize_result_results_list():
    assert summarize_result({"results": [1, 2, 3]}) == {"candidate_count": 3}


def test_summarize_result_topics_list():
    assert summarize_result({"topics": [1, 2]}) == {"topic_count": 2}


def test_summarize_result_related_topics_list():
    assert summarize_result({"related_topics": [1]}) == {"related_count": 1}


def test_summarize_result_error():
    assert summarize_result({"error": "boom"}) == {"error": "boom"}


def test_summarize_result_plain_dict_falls_back_to_keys():
    assert summarize_result({"a": 1, "b": 2}) == {"keys": ["a", "b"]}


def test_summarize_result_non_dict():
    assert summarize_result("plain string") == {"value": "plain string"}


def test_trace_recorder_pairs_before_after_and_times_it():
    recorder = TraceRecorder()
    tool = FakeTool("search_knowledge")

    recorder.before_tool(tool, {"query": "PCOS"}, tool_context=None)
    recorder.after_tool(tool, {"query": "PCOS"}, tool_context=None, result={"results": [1, 2]})

    assert len(recorder.tool_calls) == 1
    call = recorder.tool_calls[0]
    assert call["tool"] == "search_knowledge"
    assert call["args"] == {"query": "PCOS"}
    assert call["result_summary"] == {"candidate_count": 2}
    assert isinstance(call["latency_ms"], float)
    assert "_started_at" not in call


def test_trace_recorder_handles_multiple_sequential_tool_calls():
    recorder = TraceRecorder()
    search_tool = FakeTool("search_knowledge")
    topics_tool = FakeTool("query_health_topics")

    recorder.before_tool(search_tool, {"query": "x"}, tool_context=None)
    recorder.after_tool(search_tool, {"query": "x"}, tool_context=None, result={"results": []})
    recorder.before_tool(topics_tool, {}, tool_context=None)
    recorder.after_tool(topics_tool, {}, tool_context=None, result={"topics": [1, 2, 3]})

    assert [c["tool"] for c in recorder.tool_calls] == ["search_knowledge", "query_health_topics"]
    assert recorder.tool_calls[1]["result_summary"] == {"topic_count": 3}
