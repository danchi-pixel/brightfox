"""Automatic checks on a tutor reply (no AI needed). Each returns (passed, note)."""
from __future__ import annotations

import re
from typing import Any

from app.content.checker import _GENDERED_YOU

_DECIMAL_POINT = re.compile(r"\b\d+\.\d+\b")
_EN_WORDS = re.compile(r"\b(the|and|you|is|are|what|this|that|with)\b", re.IGNORECASE)
_SL_WORDS = re.compile(r"\b(je|in|da|kaj|koliko|to|na|se|ali|ti|pa)\b", re.IGNORECASE)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def decimal_comma(case: dict[str, Any], reply: str) -> tuple[bool, str]:
    if case["subject"] != "math":
        return True, "n/a"
    m = _DECIMAL_POINT.search(reply)
    return (m is None, f"decimal point: {m.group(0)}" if m else "ok")


def gender_neutral(case: dict[str, Any], reply: str) -> tuple[bool, str]:
    if case["language"] != "sl":
        return True, "n/a"
    m = _GENDERED_YOU.search(reply)
    return (m is None, f"gendered: {m.group(0)}" if m else "ok")


def no_answer_first(case: dict[str, Any], reply: str) -> tuple[bool, str]:
    """On the first ask, the final answer must not appear (hints first)."""
    answer = case.get("answer") or ""
    if not answer or sum(1 for t in case["turns"] if t["role"] == "user") > 1:
        return True, "n/a"
    core = _norm(answer).replace("x = ", "").split(" ")[0]
    pattern = re.compile(rf"(?<![\d,]){re.escape(core)}(?![\d,])")
    hit = pattern.search(_norm(reply))
    return (hit is None, f"gave '{core}'" if hit else "ok")


def language(case: dict[str, Any], reply: str) -> tuple[bool, str]:
    en, sl = len(_EN_WORDS.findall(reply)), len(_SL_WORDS.findall(reply))
    if case["language"] == "sl":
        return (sl >= en, f"sl {sl} / en {en}")
    return (en >= sl, f"en {en} / sl {sl}")


def asks_back(case: dict[str, Any], reply: str) -> tuple[bool, str]:
    return ("?" in reply, "ok" if "?" in reply else "no question")


def short(case: dict[str, Any], reply: str) -> tuple[bool, str]:
    words = len(reply.split())
    return (words <= 120, f"{words} words")


CHECKS = {"decimal_comma": decimal_comma, "gender_neutral": gender_neutral, "no_answer_first": no_answer_first,
          "language": language, "asks_back": asks_back, "short": short}


def run_checks(case: dict[str, Any], reply: str) -> dict[str, tuple[bool, str]]:
    return {name: fn(case, reply) for name, fn in CHECKS.items()}
