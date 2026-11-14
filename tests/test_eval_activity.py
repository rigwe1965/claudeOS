"""Regression tests: judge/consolidator must survive a leading thinking block; activity log must persist."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.utils import first_text


def _resp(*blocks):
    return SimpleNamespace(content=list(blocks))


THINKING = SimpleNamespace(type="thinking", thinking="hmm")          # has no .text — the old crash
TEXT = lambda t: SimpleNamespace(type="text", text=t)                # noqa: E731


def test_first_text_skips_thinking_blocks():
    assert first_text(_resp(THINKING, TEXT("answer"))) == "answer"


def test_first_text_empty_when_no_text_block():
    assert first_text(_resp(THINKING)) == ""
    assert first_text(_resp()) == ""
    assert first_text(SimpleNamespace(content=None)) == ""


def test_evaluator_scores_when_response_starts_with_thinking(fresh_db):
    from agents import evaluator
    from core.database import get_db

    with get_db() as conn:
        conn.execute("INSERT INTO agents(id,name,display_name,system_prompt) VALUES ('a1','a','A','p')")
        conn.execute("INSERT INTO agent_runs(id,agent_id,namespace,input,status) VALUES ('r1','a1','global','{}','done')")

    judge = '{"task_completion":5,"factual_grounding":5,"conciseness":4,"safety":1,"reasoning":"ok"}'
    client = MagicMock()
    client.messages.create.return_value = _resp(THINKING, TEXT(judge))
    with patch("agents.executor._get_client", return_value=client):
        evaluator._do_evaluate("r1", "prompt", "output", "")

    with get_db() as conn:
        row = conn.execute("SELECT eval_score FROM agent_runs WHERE id='r1'").fetchone()
    assert row["eval_score"] == round(5 * 0.4 + 5 * 0.3 + 4 * 0.2 + 5 * 0.1, 2)


def _judge_score(judge_json, context="", client=None):
    """Run _do_evaluate against a canned judge reply; return (eval_score, client)."""
    from agents import evaluator
    from core.database import get_db

    with get_db() as conn:
        conn.execute("INSERT INTO agents(id,name,display_name,system_prompt) VALUES ('a1','a','A','p')")
        conn.execute("INSERT INTO agent_runs(id,agent_id,namespace,input,status) VALUES ('r1','a1','global','{}','done')")
    client = client or MagicMock()
    client.messages.create.return_value = _resp(TEXT(judge_json))
    with patch("agents.executor._get_client", return_value=client):
        evaluator._do_evaluate("r1", "prompt", "output", context)
    with get_db() as conn:
        return conn.execute("SELECT eval_score FROM agent_runs WHERE id='r1'").fetchone()["eval_score"], client


def test_perfect_run_scores_five(fresh_db):
    score, _ = _judge_score('{"task_completion":5,"factual_grounding":5,"conciseness":5,"safety":1,"reasoning":"ok"}')
    assert score == 5.0


def test_unsafe_run_loses_safety_weight(fresh_db):
    score, _ = _judge_score('{"task_completion":5,"factual_grounding":5,"conciseness":5,"safety":0,"reasoning":"bad"}')
    assert score == 4.5


def test_judge_sees_full_injected_context(fresh_db):
    ctx = "x" * 2900 + "TAIL"
    _, client = _judge_score(
        '{"task_completion":5,"factual_grounding":5,"conciseness":5,"safety":1,"reasoning":"ok"}', context=ctx,
    )
    sent = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "TAIL" in sent


def test_stream_done_event_carries_memory_context(fresh_db):
    from agents import executor

    final = SimpleNamespace(usage=SimpleNamespace(input_tokens=1, output_tokens=2))
    stream = MagicMock()
    stream.__enter__.return_value.text_stream = iter(["hi"])
    stream.__enter__.return_value.get_final_message.return_value = final
    client = MagicMock()
    client.messages.stream.return_value = stream
    with patch.object(executor, "_build_memory_context", return_value="## Namespace Context\n- fact"), \
         patch.object(executor, "_get_client", return_value=client):
        chunks = list(executor.execute_stream(
            "a", "sys", "prompt", "global", "m", 100, 0.0, {},
        ))
    done = chunks[-1]
    assert done["_done"] and done["mem_context"] == "## Namespace Context\n- fact"


def test_activity_log_entry_is_stored(fresh_db):
    from agents.executor import _write_activity_log
    from core.database import get_db

    _write_activity_log("global", "qa-agent", "do a thing", "did it", 10, 20, 500)

    with get_db() as conn:
        rows = conn.execute("SELECT category, confidence FROM memory_entries WHERE key LIKE 'activity_log:%'").fetchall()
    assert len(rows) == 1
    assert rows[0]["category"] == "context"
    assert rows[0]["confidence"] < 0.8      # stays out of injected agent context


def test_numpy_is_imported_eagerly_for_semantic_search():
    # numpy 1.26 can't be safely first-imported from several threads at once; the vector store
    # imports it at module load so the first import is serialised (silent semantic-search outage).
    from memory import vector_store
    assert hasattr(vector_store, "numpy")
