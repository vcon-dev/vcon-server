"""End-to-end smoke that runs each chat-LLM conserver link against the real LLM API
and dumps the resulting agent_trace analysis entry for inspection.

Requires (loaded from .env.test or environment):
- OPENAI_API_KEY (for analyze, analyze_and_label, analyze_vcon, check_and_tag, detect_engagement)
- HUGGINGFACE_API_KEY (optional, for hugging_llm_link — skipped if missing)

Usage: uv run python scripts/agent_session_smoke.py
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Make the conserver package importable like pytest does
ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "common", ROOT / "conserver"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env.test")
load_dotenv()  # fall through to any .env

from vcon import Vcon  # this is common/vcon.py per the pythonpath


SAMPLE_TRANSCRIPT = (
    "Customer: Hi, I'm calling about my recent bill. I think there's an error. "
    "Agent: I apologize for the issue. Let me check that for you. "
    "Customer: I was charged twice for the same service on March 15th. "
    "Agent: You're right, I see the duplicate charge. I'll process a refund right away. "
    "Customer: Thank you, I appreciate that."
)


def _fresh_vcon() -> Vcon:
    v = Vcon.build_new()
    v.vcon_dict["dialog"].append({
        "type": "text",
        "parties": [0],
        "start": "2026-05-18T10:00:00Z",
        "body": SAMPLE_TRANSCRIPT,
        "encoding": "none",
    })
    v.vcon_dict["analysis"].append({
        "dialog": 0,
        "type": "transcript",
        "vendor": "openai-whisper",
        "body": {"paragraphs": {"transcript": SAMPLE_TRANSCRIPT}, "transcript": SAMPLE_TRANSCRIPT},
        "encoding": "none",
    })
    return v


def _patched_redis(module_path: str, vcon: Vcon):
    """Patch VconRedis in a given link module to return our fixture vcon."""
    p = patch(f"{module_path}.VconRedis")
    mock_cls = p.start()
    instance = Mock()
    instance.get_vcon.return_value = vcon
    instance.store_vcon = Mock()
    mock_cls.return_value = instance
    return p


def _dump_agent_trace(label: str, vcon: Vcon) -> None:
    print(f"\n{'='*70}\n{label}\n{'='*70}")
    traces = [a for a in vcon.analysis if a["type"] == "agent_trace"]
    if not traces:
        print("  (no agent_trace emitted)")
        return
    entry = traces[0]
    decoded_body = json.loads(entry["body"])
    summary = {
        "type": entry["type"],
        "dialog": entry["dialog"],
        "vendor": entry["vendor"],
        "product": entry.get("product"),
        "schema": entry.get("schema"),
        "encoding": entry.get("encoding"),
        "body (decoded)": decoded_body,
    }
    print(json.dumps(summary, indent=2))
    agent_parties = [p for p in vcon.parties if p.get("role") == "agent"]
    print(f"  agent parties: {len(agent_parties)} — meta.agent_session = {json.dumps(agent_parties[0]['meta']['agent_session'])}")
    print(f"  extensions: {vcon.vcon_dict.get('extensions')}")


def run_analyze() -> None:
    from links import analyze
    v = _fresh_vcon()
    p = _patched_redis("links.analyze", v)
    try:
        analyze.run("smoke-uuid", "analyze", {
            "prompt": "Summarize this customer service interaction in one sentence.",
            "analysis_type": "summary",
            "model": "gpt-4o-mini",
            "temperature": 0,
            "system_prompt": "You are a helpful assistant.",
            "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
        })
    finally:
        p.stop()
    _dump_agent_trace("analyze (OpenAI gpt-4o-mini)", v)


def run_analyze_and_label() -> None:
    from links import analyze_and_label
    v = _fresh_vcon()
    p = _patched_redis("links.analyze_and_label", v)
    try:
        analyze_and_label.run("smoke-uuid", "analyze_and_label", {
            "model": "gpt-4o-mini",
            "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
        })
    finally:
        p.stop()
    _dump_agent_trace("analyze_and_label (OpenAI gpt-4o-mini)", v)


def run_analyze_vcon() -> None:
    from links import analyze_vcon
    v = _fresh_vcon()
    p = _patched_redis("links.analyze_vcon", v)
    try:
        analyze_vcon.run("smoke-uuid", "analyze_vcon", {
            "model": "gpt-4o-mini",
            "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
        })
    finally:
        p.stop()
    _dump_agent_trace("analyze_vcon (OpenAI gpt-4o-mini)", v)


def run_check_and_tag() -> None:
    from links import check_and_tag
    v = _fresh_vcon()
    p = _patched_redis("links.check_and_tag", v)
    try:
        check_and_tag.run("smoke-uuid", "check_and_tag", {
            "model": "gpt-4o-mini",
            "tag_name": "topic",
            "tag_value": "billing",
            "evaluation_question": "Is this conversation about a billing issue?",
            "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
        })
    finally:
        p.stop()
    _dump_agent_trace("check_and_tag (OpenAI gpt-4o-mini)", v)


def run_detect_engagement() -> None:
    from links import detect_engagement
    v = _fresh_vcon()
    p = _patched_redis("links.detect_engagement", v)
    try:
        detect_engagement.run("smoke-uuid", "detect_engagement", {
            "model": "gpt-4.1",
            "OPENAI_API_KEY": os.environ["OPENAI_API_KEY"],
        })
    finally:
        p.stop()
    _dump_agent_trace("detect_engagement (OpenAI gpt-4.1)", v)


def run_hugging_llm_link() -> None:
    if not os.environ.get("HUGGINGFACE_API_KEY"):
        print("\n[skip] hugging_llm_link — HUGGINGFACE_API_KEY not set")
        return
    from links.hugging_llm_link import VConLLMProcessor, LLMConfig
    v = _fresh_vcon()
    cfg = LLMConfig.from_dict({"HUGGINGFACE_API_KEY": os.environ["HUGGINGFACE_API_KEY"]})
    proc = VConLLMProcessor(cfg)
    proc.vcon_redis = Mock()
    proc.vcon_redis.get_vcon.return_value = v
    proc.vcon_redis.store_vcon = Mock()
    proc.process_vcon("smoke-uuid", "hugging_llm_link")
    _dump_agent_trace("hugging_llm_link (HuggingFace Llama-2-70b)", v)


def main():
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set in environment or .env.test", file=sys.stderr)
        sys.exit(1)

    for fn in (
        run_analyze,
        run_analyze_and_label,
        run_analyze_vcon,
        run_check_and_tag,
        run_detect_engagement,
        run_hugging_llm_link,
    ):
        try:
            fn()
        except Exception as e:
            print(f"\n[error] {fn.__name__}: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
