#!/usr/bin/env python3
"""Merge all extraction sources into public/exam.json.

Sources:
  /tmp/grile_raw.json            deterministic highlight detector (grile section A, p1-65)
  /tmp/extract/grileAfix-*.json  vision re-extraction of flagged section-A pages
  /tmp/extract/grileB-*.json     vision extraction of grile section B (p66-79)
  /tmp/extract/semio-*.json      vision extraction of semio (p1-63)

Output question schema (multi-answer + backwards compatible):
  { test, source, number?, type?, question, options{}, correct_answers[], correct_answer }
"""
import json
import glob
import re
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAGGED = {10, 15, 18, 25, 29, 39, 65}

problems = []


def load(path):
    try:
        return json.load(open(path))
    except Exception as e:
        problems.append(f"BAD JSON {path}: {e}")
        return None


def norm_q(stem):
    return re.sub(r"[^a-z0-9]", "", (stem or "").lower())


def clean(q, test, source):
    """Validate + normalize one question dict into the final schema."""
    opts = {k: v for k, v in (q.get("options") or {}).items() if v and str(v).strip()}
    ca = [c for c in (q.get("correct_answers") or []) if c in opts]
    rec = {
        "test": test,
        "source": source,
        "question": (q.get("question") or "").strip(),
        "options": opts,
        "correct_answers": ca,
        "correct_answer": ca[0] if ca else "",
    }
    if q.get("number") is not None:
        rec["number"] = q["number"]
    if q.get("type"):
        rec["type"] = q["type"]
    # validation
    tag = f"{source} {test} n={q.get('number')} '{rec['question'][:40]}'"
    if len(opts) < 2:
        problems.append(f"FEW OPTS ({len(opts)}): {tag}")
    if not ca:
        problems.append(f"NO CORRECT: {tag}")
    if q.get("type", "").startswith("simpl") and len(ca) != 1:
        problems.append(f"SIMPLU but {len(ca)} correct: {tag}")
    return rec


def grile_section_a():
    det = load("/tmp/grile_raw.json") or []
    out = []
    # trusted detector questions on non-flagged pages
    for q in det:
        if q["page"] not in FLAGGED:
            out.append(clean(q, "Grile Chirurgie", "grile"))
    # flagged pages: prefer vision; fall back to complete detector question by number
    for p in sorted(FLAGGED):
        vf = load(f"/tmp/extract/grileAfix-{p:03d}.json")
        det_p = [q for q in det if q["page"] == p]
        if not vf:
            problems.append(f"MISSING grileAfix-{p:03d}.json; using detector for page {p}")
            for q in det_p:
                if q.get("number") is not None:
                    out.append(clean(q, "Grile Chirurgie", "grile"))
            continue
        for vq in vf.get("questions", []):
            if vq.get("options"):
                out.append(clean(vq, "Grile Chirurgie", "grile"))
            else:
                cand = [d for d in det_p
                        if d.get("number") == vq.get("number") and d.get("options")]
                if cand:
                    out.append(clean(cand[0], "Grile Chirurgie", "grile"))
                else:
                    problems.append(f"INCOMPLETE flagged q p{p} n={vq.get('number')}")
                    out.append(clean(vq, "Grile Chirurgie", "grile"))
    return out


def grile_section_b():
    out = []
    seen = {}
    for path in sorted(glob.glob("/tmp/extract/grileB-*.json")):
        data = load(path)
        if not data:
            continue
        for q in data.get("questions", []):
            key = norm_q(q.get("question"))
            if not key:
                continue
            rec = clean(q, "Grile Chirurgie", "grile")
            if key in seen:
                # keep the variant with more options / answers
                prev = seen[key]
                if len(rec["options"]) > len(prev["options"]):
                    out[out.index(prev)] = rec
                    seen[key] = rec
                continue
            seen[key] = rec
            out.append(rec)
    return out


def semio():
    out = []
    for path in sorted(glob.glob("/tmp/extract/semio-*.json")):
        data = load(path)
        if not data:
            problems.append(f"MISSING/BAD {path}")
            continue
        for q in data.get("questions", []):
            out.append(clean(q, "Semiologie Chir", "semio"))
    return out


def main():
    a = grile_section_a()
    b = grile_section_b()
    s = semio()
    allq = a + b + s
    # drop questions with no usable answer or too few options
    final = [q for q in allq if q["correct_answers"] and len(q["options"]) >= 2]
    dropped = len(allq) - len(final)

    out_path = os.path.join(ROOT, "public", "exam.json")
    json.dump(final, open(out_path, "w"), ensure_ascii=False, indent=2)

    print(f"grile A : {len(a)}")
    print(f"grile B : {len(b)}")
    print(f"semio   : {len(s)}")
    print(f"total   : {len(allq)}  -> written {len(final)} (dropped {dropped})")
    multi = sum(1 for q in final if len(q["correct_answers"]) > 1)
    print(f"multi-answer: {multi}   single: {len(final) - multi}")
    print(f"wrote {out_path}")
    if problems:
        print(f"\n--- {len(problems)} problems flagged ---")
        for p in problems:
            print("  ", p)


if __name__ == "__main__":
    main()
