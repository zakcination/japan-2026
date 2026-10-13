"""The DeepSeek adapter (supabase/functions/assistant/deepseek.mjs): Anthropic-shaped loop in, chat-completions out and back."""
import json, shutil, subprocess
import pytest
from conftest import ROOT

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="node not installed")
MOD = (ROOT / "supabase/functions/assistant/deepseek.mjs").as_uri()


def js(code):
    r = subprocess.run([NODE, "--input-type=module", "-e", f"import * as D from '{MOD}';\n{code}"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_request_keeps_system_tools_and_tool_round_trips():
    body = {"model": "x", "max_tokens": 4000, "system": [{"type": "text", "text": "SYS", "cache_control": {"type": "ephemeral"}}, {"type": "text", "text": "CTX"}],
            "tools": [{"name": "get_day", "description": "d", "input_schema": {"type": "object", "properties": {"n": {"type": "integer"}}}},
                      {"type": "web_search_20260209", "name": "web_search"}],
            "messages": [{"role": "user", "content": [{"type": "image", "source": {}}, {"type": "text", "text": "Что сегодня?"}]},
                         {"role": "assistant", "content": [{"type": "thinking", "thinking": "…"}, {"type": "text", "text": "Смотрю."},
                                                           {"type": "tool_use", "id": "t1", "name": "get_day", "input": {"n": 3}}]},
                         {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "день 3"}]}]}
    r = js(f"console.log(JSON.stringify(D.toDeepSeek({json.dumps(body)})))")
    assert r["model"] == "deepseek-chat" and r["max_tokens"] == 4000
    assert r["messages"][0] == {"role": "system", "content": "SYS\nCTX"}
    assert "не видит изображений" in r["messages"][1]["content"] and r["messages"][1]["content"].endswith("Что сегодня?")
    a = r["messages"][2]
    assert a["role"] == "assistant" and a["content"] == "Смотрю." and a["tool_calls"][0]["function"] == {"name": "get_day", "arguments": '{"n":3}'}
    assert r["messages"][3] == {"role": "tool", "tool_call_id": "t1", "content": "день 3"}
    assert [t["function"]["name"] for t in r["tools"]] == ["get_day"]                    # the hosted web search is dropped


def test_reply_becomes_text_or_tool_use():
    r = js("""console.log(JSON.stringify([
      D.fromDeepSeek({choices: [{finish_reason: 'stop', message: {content: 'Привет'}}], usage: {prompt_tokens: 10, completion_tokens: 2}}),
      D.fromDeepSeek({choices: [{finish_reason: 'tool_calls', message: {content: '', tool_calls: [{id: 'c1', function: {name: 'get_day', arguments: '{"n":2}'}}]}}]}),
      D.fromDeepSeek({choices: [{finish_reason: 'tool_calls', message: {tool_calls: [{id: 'c2', function: {name: 'x', arguments: '{bad'}}]}}]}),
    ]))""")
    assert r[0] == {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Привет"}],
                    "usage": {"input_tokens": 10, "output_tokens": 2, "cache_read_input_tokens": 0}}
    assert r[1]["stop_reason"] == "tool_use" and r[1]["content"] == [{"type": "tool_use", "id": "c1", "name": "get_day", "input": {"n": 2}}]
    assert r[2]["content"][0]["input"] == {}                                                # malformed arguments never crash the loop
