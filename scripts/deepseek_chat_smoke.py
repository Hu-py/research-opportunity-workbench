"""Manual, low-cost DeepSeek chat smoke using existing encrypted model vault.

Default mode only checks whether a key is stored; --live explicitly makes
three short paid calls. Run in the backend environment that already has
DATABASE_URL and MODEL_VAULT_KEY. No key or complete response is printed.
"""
from __future__ import annotations

import argparse
import json

from backend.deepseek_chat_probe import ChatProbeError, chat_turn
from backend.model_vault import load_key, status
from research_workbench.core import session_factory


PROMPTS = [
    "我的测试代号是 ATLAS-7Q42。请记住，回答‘已记录’。",
    "我的测试代号是什么？请只回答代号。",
    "这个代号来自本次对话的哪一轮？请简短回答。",
]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Safe DeepSeek chat probe")
    parser.add_argument("--live", action="store_true", help="Opt in to three paid API calls")
    args = parser.parse_args(argv)
    with session_factory()() as db:
        info = status(db)
        configured = bool(info["configured"] and info["vault_ready"])
        print(json.dumps({"probe": "deepseek_chat_v01", "configured": configured,
                          "model": "deepseek-flash", "live_requested": args.live},
                         ensure_ascii=False))
        if not configured:
            return 2
        if not args.live:
            return 0
        try:
            key = load_key(db)
        except ValueError:
            print("MODEL_VAULT_DECRYPTION_FAILED")
            return 2
    if not key:
        return 2

    history = []
    total_input = 0
    total_output = 0
    correct = False
    try:
        for i, prompt in enumerate(PROMPTS, start=1):
            history.append({"role": "user", "content": prompt})
            reply, usage = chat_turn(api_key=key, history=history)
            history.append({"role": "assistant", "content": reply})
            total_input += usage["input_tokens"]
            total_output += usage["output_tokens"]
            if i == 2:
                correct = "ATLAS-7Q42" in reply
            print(json.dumps({"round": i, "answer_present": bool(reply.strip()),
                              "history_messages": len(history),
                              "input_tokens": usage["input_tokens"],
                              "output_tokens": usage["output_tokens"]}, ensure_ascii=False))
    except ChatProbeError as exc:
        print(json.dumps({"status": "provider_error", "detail": str(exc)}, ensure_ascii=False))
        return 1
    finally:
        key = None
    print(json.dumps({"status": "passed" if correct else "failed_context_recall",
                      "context_recall_passed": correct,
                      "total_input_tokens": total_input,
                      "total_output_tokens": total_output}, ensure_ascii=False))
    return 0 if correct else 1


if __name__ == "__main__":
    raise SystemExit(main())
