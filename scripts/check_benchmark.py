"""Check hand-written benchmark questions before anything runs: no model is called, so no credits are spent. The records are
opened read-only. See docs/benchmark_data_guide.md.
  uv run python scripts/check_benchmark.py benchmark/questions_v1.jsonl
  uv run python scripts/check_benchmark.py benchmark/questions_v1.jsonl --show      # also prints each computed answer
  uv run python scripts/check_benchmark.py --schema T01                             # the tables and columns answer_sql can use
Reference answers are computed over the agent's own sandbox tables (anubhav.eval.reference), the same for every company.
"""

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

from anubhav.data.config import ROOT
from anubhav.eval.reference import reference_sandbox, run_reference_sql
from anubhav.runtime.broker import REGISTRY
from anubhav.runtime.query import QueryError

WORLD = ROOT / "data" / "worlds" / "full_seed7919"
COMPANIES = {"T01", "T02"}
LANGS = {"rt", "te", "en"}
SPLITS = {"dev", "test", "example"}
CATEGORIES = {"tool_trap": "number_or_name", "false_premise": "false", "ambiguous": "ask"}
TARGET = {"tool_trap": 16, "false_premise": 12, "ambiguous": 12}
REQUIRED = {"id", "company", "split", "category", "lang", "town", "question", "answer_kind", "answer_sql", "why_hard"}
BANNED_SQL = ("truth", "attach", "hidden_rules", "canonical", "true_site_profiles")


def rows_for(world, company, sql):
    """The rows the agent itself would get: the company's sandbox tables, one read-only SELECT."""
    return run_reference_sql(world, company, sql)


def print_schema(world, company):
    sb = reference_sandbox(world, company)
    for name, m in sb.tables.items():
        print(f"{name} ({m['rows']} rows): {', '.join(m['columns'])}")


def answer_problem(kind, rows):
    """The computed answer must be one clear value, or the question can't be scored fairly."""
    if kind == "number":
        if len(rows) != 1 or len(rows[0]) != 1 or not isinstance(rows[0][0], int | float):
            return "number: the SQL must return one row with one number"
    elif kind == "name":
        if not rows or any(len(r) != 2 for r in rows):
            return "name: the SQL must return rows of (answer, value), best first"
        if len(rows) > 1 and rows[0][1] == rows[1][1]:
            return f"name: tie for first place ({rows[0][0]}, {rows[1][0]}), so there is no single right answer"
    elif kind == "false":
        if len(rows) != 1 or rows[0][0] != 0:
            return f"false: the SQL must count what the question wrongly assumes and return 0, got {rows[:2]}"
    elif kind == "ask":
        if len(rows) != 1 or not isinstance(rows[0][0], int) or rows[0][0] < 2:
            return f"ask: the SQL must count the possible meanings and return 2 or more, got {rows[:2]}"
    else:
        return f"unknown answer_kind {kind!r}"
    return None


def check(lines, world=WORLD):
    """Returns (problems, warnings, questions with their computed answers)."""
    problems, warnings, questions = [], [], []
    tools = {t.name for t in REGISTRY}
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            q = json.loads(line)
        except ValueError as e:
            problems.append(f"line {n}: not valid JSON ({e})")
            continue
        where = q.get("id", f"line {n}")
        missing = REQUIRED - set(q)
        if missing:
            problems.append(f"{where}: missing {sorted(missing)}")
            continue
        for field, allowed in (("company", COMPANIES), ("lang", LANGS), ("split", SPLITS), ("category", set(CATEGORIES))):
            if q[field] not in allowed:
                problems.append(f"{where}: {field} must be one of {sorted(allowed)}")
        if not q["question"].strip() or not q["why_hard"].strip():
            problems.append(f"{where}: question and why_hard can't be empty")
        if q["category"] in CATEGORIES:
            allowed_kinds = {"number", "name"} if q["category"] == "tool_trap" else {CATEGORIES[q["category"]]}
            if q["answer_kind"] not in allowed_kinds:
                problems.append(f"{where}: {q['category']} needs answer_kind in {sorted(allowed_kinds)}")
        if q["category"] == "tool_trap":
            bad = set(q.get("right_tools", [])) - tools
            if not q.get("right_tools"):
                problems.append(f"{where}: tool_trap needs right_tools")
            elif bad:
                problems.append(f"{where}: unknown tools {sorted(bad)}")
        low = q["answer_sql"].lower()
        if any(b in low for b in BANNED_SQL):
            problems.append(f"{where}: answer_sql may use only the company's own records, never the hidden truth")
            continue
        if q["company"] in COMPANIES:
            try:
                q["computed"] = rows_for(world, q["company"], q["answer_sql"])
            except (sqlite3.Error, QueryError) as e:
                problems.append(f"{where}: SQL failed: {e}")
                continue
            if p := answer_problem(q["answer_kind"], q["computed"]):
                problems.append(f"{where}: {p}")
        questions.append(q)
    for field in ("id", "question"):
        for value, count in Counter(q[field] for q in questions).items():
            if count > 1:
                problems.append(f"repeated {field}: {value[:60]}")
    real = [q for q in questions if q["split"] != "example"]
    towns = defaultdict(lambda: defaultdict(set))
    for q in real:
        if q["town"]:
            towns[q["company"]][q["split"]].add(q["town"])
    for company, by_split in towns.items():
        if shared := by_split["dev"] & by_split["test"]:
            problems.append(f"{company}: town in both dev and test: {sorted(shared)}")
    for category, want in TARGET.items():
        have = Counter(q["split"] for q in real if q["category"] == category)
        if have["dev"] != want // 2 or have["test"] != want // 2:
            warnings.append(f"{category}: {have['dev']} dev and {have['test']} test, target {want // 2} of each")
    for split in ("dev", "test"):
        langs = Counter(q["lang"] for q in real if q["split"] == split)
        if real and any(not langs[x] for x in LANGS):
            warnings.append(f"{split}: not all languages are used: {dict(langs)}")
    return problems, warnings, questions


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Check benchmark questions. No model is called.")
    ap.add_argument("path", type=Path, nargs="?")
    ap.add_argument("--show", action="store_true", help="print each computed answer")
    ap.add_argument("--schema", metavar="COMPANY", help="print the tables and columns answer_sql can use, then exit")
    a = ap.parse_args(argv)
    if not a.schema and a.path is None:
        ap.error("give a questions file, or --schema COMPANY")
    if not (WORLD / "manifest.json").exists():
        print("The test world is missing. Make it with: uv run python -m anubhav.data.generate --full --seed 7919")
        return 2
    if a.schema:
        if a.schema not in COMPANIES:
            ap.error(f"--schema must be one of {sorted(COMPANIES)}")
        print_schema(WORLD, a.schema)
        return 0
    problems, warnings, questions = check(a.path.read_text(encoding="utf-8").splitlines())
    if a.show:
        for q in questions:
            print(f"{q['id']:18} {q['answer_kind']:7} {q.get('computed', [])[:3]}")
    for w in warnings:
        print("note ", w)
    for p in problems:
        print("FAIL ", p)
    print(f"{len(questions)} questions, {len(problems)} problems, {len(warnings)} notes")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
