"""Finds assignments/exams that two or more members share, for the dashboard's
"Check for work" button.

Matching is done here, in code, not by the agent: the agent only ever sees
the matches, never anyone's unmatched calendar items, so it can't leak "Jeff
has a chem test" to someone who doesn't. Two items match when they belong to
different members, are due within 48 hours of each other (plan.md's "same
crunch period"), and look like the same piece of work:
  - same course code (CS101 / cs-101), and no conflicting type
    (midterm vs final) or number (Assignment 2 vs Assignment 3), or
  - no course code, but at least half their distinctive words in common
    ("Organic chemistry lab report" ~ "Lab report - organic chemistry").
Bare generic titles ("Exam", "Assignment due") never match on their own.
"""

import os
import re
from datetime import datetime, timedelta, timezone

import groups
from agent.context import get_group_id, get_session_id
from skills_impl.calendar_skill import get_academic_items

MATCH_WINDOW = timedelta(hours=48)

_SYNONYMS = [
    (re.compile(r"\bmid[\s-]?(?:term|sem(?:ester)?)s?\b"), "midterm"),
    (re.compile(r"\bend[\s-]?(?:term|sem(?:ester)?)s?\b|\bfinals?\b"), "final"),
    (re.compile(r"\b(?:homework|hw)(?=\d|\b)"), "assignment "),  # "HW3" -> "assignment 3"
    (re.compile(r"\b(?:problem sets?|psets?)\b"), "assignment"),
    (re.compile(r"\b(?:quizzes)\b"), "quiz"),
]
_TYPE_WORDS = {
    "assignment", "assignments", "midterm", "final", "exam", "exams", "quiz", "test", "tests",
    "project", "projects", "lab", "labs", "viva", "presentation", "presentations", "essay",
    "essays", "report", "reports", "paper", "papers",
}
# words that say nothing about *which* piece of work it is
_GENERIC_WORDS = {
    "due", "deadline", "deadlines", "submit", "submission", "submissions", "today", "tomorrow", "tonight", "the", "a", "an",
    "for", "of", "and", "on", "at", "in", "to", "my", "our", "class", "course", "prep", "study",
    "reminder", "hand", "turn", "no", "part", "pt",
}
# "exam" is the umbrella word: compatible with midterm/final/quiz/test
_TYPE_FAMILY = {"exam": "exam", "exams": "exam", "midterm": "midterm", "final": "final", "quiz": "quiz",
                "test": "test", "tests": "test"}
_COURSE_CODE_RE = re.compile(r"\b([a-z]{2,5})[\s-]?(\d{2,4}[a-z]?)\b")
_NON_COURSE_PREFIXES = {"hw", "lab", "labs", "quiz", "test", "pset", "part", "pt", "unit", "week", "ch", "chapter",
                        "assignment", "project", "sec", "section"}


def _normalise(title: str) -> dict:
    text = title.lower()
    for pattern, replacement in _SYNONYMS:
        text = pattern.sub(replacement, text)
    codes = {f"{a}{n}" for a, n in _COURSE_CODE_RE.findall(text) if a not in _NON_COURSE_PREFIXES}
    words = re.findall(r"[a-z]+|\d+", text)
    types = {_TYPE_FAMILY.get(w, w.rstrip("s")) for w in words if w in _TYPE_WORDS}
    numbers = {w for w in words if w.isdigit()} - {n for code in codes for n in re.findall(r"\d+", code)}
    content = {w for w in words if w.isalpha() and w not in _TYPE_WORDS and w not in _GENERIC_WORDS and len(w) > 1}
    content -= {re.match(r"[a-z]+", c).group() for c in codes}
    return {"codes": codes, "types": types, "numbers": numbers, "content": content}


def _types_compatible(a: set, b: set) -> bool:
    if not a or not b or a & b:
        return True
    # "exam" is compatible with any specific exam kind, but midterm != final
    exam_kinds = {"midterm", "final", "quiz", "test"}
    return ("exam" in a and b <= exam_kinds | {"exam"}) or ("exam" in b and a <= exam_kinds | {"exam"})


def _same_work(a: dict, b: dict) -> bool:
    if not _types_compatible(a["types"], b["types"]):
        return False
    if a["numbers"] and b["numbers"] and not a["numbers"] & b["numbers"]:
        return False
    if a["codes"] and b["codes"]:
        return bool(a["codes"] & b["codes"])
    words_a = a["content"] | a["codes"]
    words_b = b["content"] | b["codes"]
    shared = words_a & words_b
    if not shared:
        return False
    return len(shared) / len(words_a | words_b) >= 0.5


def _parse_due(value: str) -> datetime:
    if len(value) == 10:  # all-day event: YYYY-MM-DD
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def match_shared_work(items_by_member: dict[str, list[dict]]) -> list[dict]:
    """items_by_member: {member name: [{"title", "due"}]} -> list of matches,
    each shared by 2+ different members. Pure function, no I/O."""
    flat = []
    for person, items in items_by_member.items():
        for item in items:
            try:
                due = _parse_due(item["due"])
            except (KeyError, ValueError):
                continue
            flat.append({"person": person, "title": item["title"], "due": due, "norm": _normalise(item["title"])})

    parent = list(range(len(flat)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(flat)):
        for j in range(i + 1, len(flat)):
            a, b = flat[i], flat[j]
            if a["person"] == b["person"] or abs(a["due"] - b["due"]) > MATCH_WINDOW:
                continue
            if _same_work(a["norm"], b["norm"]):
                parent[find(i)] = find(j)

    clusters: dict[int, list[dict]] = {}
    for i, item in enumerate(flat):
        clusters.setdefault(find(i), []).append(item)

    matches = []
    for cluster in clusters.values():
        people = sorted({c["person"] for c in cluster})
        if len(people) < 2:
            continue
        cluster.sort(key=lambda c: c["due"])
        titles_by_member = {}
        for c in cluster:
            titles_by_member.setdefault(c["person"], c["title"])
        matches.append({
            "title": cluster[0]["title"],
            "due": cluster[0]["due"].isoformat(),
            "members": people,
            "titles_by_member": titles_by_member,
        })
    matches.sort(key=lambda m: m["due"])
    for n, match in enumerate(matches, start=1):
        match["match_id"] = f"match_{n}"
    return matches


def find_shared_deadlines(days_ahead: int = 14) -> dict:
    group = groups.get_group(get_group_id())
    if group is None:
        return {"error": "Unknown group"}
    days_ahead = max(1, min(int(days_ahead), 30))

    if os.getenv("MOCK_MODE", "true").lower() == "true":
        return {"matches": [], "note": "MOCK_MODE is on, so no real calendars were read."}

    items_by_member, not_connected, unreadable = {}, [], []
    for member in group["members"]:
        try:
            items_by_member[member["name"]] = get_academic_items(member, days_ahead)
        except LookupError:
            not_connected.append(member["name"])
        except Exception:
            unreadable.append(member["name"])

    matches = match_shared_work(items_by_member)
    groups.save_study_matches(group["id"], get_session_id(), matches)
    return {
        "window_days": days_ahead,
        "checked": sorted(items_by_member),
        "not_connected": not_connected,
        "could_not_read": unreadable,
        "matches": matches,
    }
