#!/usr/bin/env python3
"""Extract questions from 'toate grilele' PDF + detect highlighted (correct) answers.

Rule: an option is correct only if its answer TEXT (not just the letter) is
highlighted yellow start-to-end. We measure yellow coverage over the answer
words that follow the leading 'x)' letter token.

Output: JSON list of questions, each with options{a..e}, correct_answers[],
plus per-option highlight score and an `ambiguous` flag for human/vision review.
"""
import sys
import re
import json
import fitz
import numpy as np

PDF = "pdfs/toate grilele chir fmm de viata.pdf"
Z = 3.0
HI = 0.5          # answer-text coverage >= HI  -> highlighted/correct
LO = 0.25         # below LO -> definitely not; between LO..HI -> ambiguous

OPT_RE = re.compile(r"^([a-eA-E])[\).]")
Q_RE = re.compile(r"^[`´'\"‘’\*\s]*(\d{1,3})\.(?=\D|$)")


def yellow_mask(page):
    pix = page.get_pixmap(matrix=fitz.Matrix(Z, Z))
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    R, G, B = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int)
    return (R >= 170) & (G >= 150) & (B <= 160) & ((R - B) > 55) & ((G - B) > 40)


def cov(mask, w):
    px0, py0 = int(w[0] * Z), int(w[1] * Z)
    px1, py1 = int(round(w[2] * Z)), int(round(w[3] * Z))
    sub = mask[py0:py1, px0:px1]
    return float(sub.mean()) if sub.size else 0.0


BULLETS = "•∙·*‣▪◦○●-—•●▪ "


def collect_lines():
    """Return ordered lines across all pages. Each line: list of token dicts."""
    doc = fitz.open(PDF)
    lines = []
    for pno in range(doc.page_count):
        page = doc[pno]
        words = page.get_text("words")
        if not words:
            continue
        mask = yellow_mask(page)
        groups = {}
        for w in words:
            key = (w[5], w[6])  # block, line
            groups.setdefault(key, []).append(w)
        for key in sorted(groups):
            ws = sorted(groups[key], key=lambda w: w[7])
            toks = [{"page": pno + 1, "text": w[4], "cov": cov(mask, w)} for w in ws]
            lines.append(toks)
    doc.close()
    return lines


def segment(lines):
    """Group lines into question stems and options. Handles bullets and wrapping.

    A question with a missing number is recovered when an option letter resets
    (a new 'a)' appears, or a letter not greater than the last one seen).
    """
    questions = []
    cur_q = None
    cur_seg = None  # 'stem' or 'opt'

    def start_q(number, stem_toks):
        nonlocal cur_q, cur_seg
        cur_q = {"number": number, "stem_toks": list(stem_toks), "options": [], "last": ""}
        questions.append(cur_q)
        cur_seg = "stem"

    for toks in lines:
        if not toks:
            continue
        i0 = 0
        while i0 < len(toks) and toks[i0]["text"].strip(BULLETS) == "":
            i0 += 1
        if i0 >= len(toks):
            continue
        head = toks[i0]["text"].lstrip(BULLETS)
        mo = OPT_RE.match(head)
        mq = Q_RE.match(head)
        if mq and not mo:
            start_q(int(mq.group(1)), toks)
            continue
        if cur_q is None:
            continue
        if mo:
            letter = mo.group(1).lower()
            # letter reset -> a new (number-less) question began
            if cur_q["options"] and letter <= cur_q["last"]:
                start_q(None, [])
            cur_q["options"].append({
                "letter": letter,
                "letter_tok": toks[i0],
                "toks": toks[i0 + 1:],
            })
            cur_q["last"] = letter
            cur_seg = "opt"
            continue
        if cur_seg == "stem":
            cur_q["stem_toks"].extend(toks)
        elif cur_q["options"]:
            cur_q["options"][-1]["toks"].extend(toks)
    return questions


def _head_remainder(o):
    head = o["letter_tok"]["text"].lstrip(BULLETS)
    return OPT_RE.sub("", head, count=1)  # text glued after 'x)' / 'x.'


def opt_text(o):
    parts = [_head_remainder(o)] + [t["text"] for t in o["toks"]]
    s = " ".join(p for p in parts if p)
    return re.sub(r"\s+", " ", s).strip()


def opt_score(o):
    """Coverage of answer words after the leading letter token.

    Decoys highlight only the 'x)' letter -> answer words score ~0.
    Real answers are highlighted start-to-end -> answer words score high.
    """
    rest = o["toks"]
    if rest:
        return sum(t["cov"] for t in rest) / len(rest)
    return o["letter_tok"]["cov"]  # single glued token like 'a)Disfagie'


def stem_text(q):
    s = " ".join(t["text"] for t in q["stem_toks"])
    s = Q_RE.sub("", s, count=1)
    s = re.sub(r"^[`´'\"‘’]+", "", s).strip()
    return re.sub(r"\s+", " ", s)


def main():
    lines = collect_lines()
    questions = segment(lines)
    out = []
    for q in questions:
        opts = {}
        correct = []
        scores = {}
        ambiguous = False
        for o in q["options"]:
            L = o["letter"]
            if L in opts:
                continue
            opts[L] = opt_text(o)
            sc = round(opt_score(o), 3)
            scores[L] = sc
            if sc >= HI:
                correct.append(L)
            elif LO <= sc < HI:
                ambiguous = True
        page_set = ({t["page"] for t in q["stem_toks"]} |
                    {t["page"] for o in q["options"] for t in o["toks"]})
        pages = sorted(page_set) or [999]
        if pages[0] > 65:        # section B (unnumbered/bulleted) -> handled by vision
            continue
        rec = {
            "test": "Toate grilele chir",
            "number": q["number"],
            "page": pages[0],
            "pages": pages,
            "question": stem_text(q),
            "options": opts,
            "correct_answers": sorted(correct),
            "scores": scores,
            "ambiguous": (ambiguous or len(correct) == 0 or len(opts) < 4
                          or q["number"] is None or not stem_text(q)),
        }
        out.append(rec)
    json.dump(out, open("/tmp/grile_raw.json", "w"), ensure_ascii=False, indent=2)
    nq = len(out)
    namb = sum(1 for r in out if r["ambiguous"])
    nzero = sum(1 for r in out if not r["correct_answers"])
    print(f"questions={nq}  ambiguous={namb}  zero_answer={nzero}")
    print("numbers:", [r["number"] for r in out][:60])
    if "-v" in sys.argv:
        for r in out:
            if r["ambiguous"]:
                print(f"\nQ{r['number']} p{r['page']} correct={r['correct_answers']} scores={r['scores']}")
                print("  ", r["question"][:90])
                for k, v in r["options"].items():
                    print(f"   {k}) {v[:70]}")


if __name__ == "__main__":
    main()
