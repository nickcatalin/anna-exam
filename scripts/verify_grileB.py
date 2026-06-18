#!/usr/bin/env python3
"""Cross-check grile section-B (vision) answers with deterministic highlight coverage.

Vision parsed the unnumbered/bulleted section-B questions well, but can mis-judge which
options are highlighted. Here we re-measure each option's yellow coverage from the PDF
(pixel-precise) and override correct_answers. Matching: each vision option text is located
among the PDF lines on its page (and the next page, for spill-over) by word overlap.
"""
import json
import glob
import re
import fitz
import numpy as np

PDF = "pdfs/toate grilele chir fmm de viata.pdf"
Z = 3.0
HI = 0.5
BULLETS = "•∙·*‣▪◦○●-—• "
OPT_RE = re.compile(r"^([a-eA-E])[\).]")


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


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).split()


def page_lines(doc, pno):
    """Lines on a page: {words:[(text,cov)], normwords:set}. cov excludes bullet/letter."""
    page = doc[pno]
    words = page.get_text("words")
    if not words:
        return []
    mask = yellow_mask(page)
    groups = {}
    for w in words:
        groups.setdefault((w[5], w[6]), []).append(w)
    out = []
    for key in sorted(groups):
        ws = sorted(groups[key], key=lambda w: w[7])
        toks = [(w[4], cov(mask, w)) for w in ws]
        text = " ".join(t for t, _ in toks)
        out.append({"toks": toks, "text": text, "nw": norm(text)})
    return out


def answer_cov(line):
    """Mean coverage of a line's tokens, skipping a leading bullet and a leading letter."""
    toks = line["toks"]
    i = 0
    while i < len(toks) and toks[i][0].strip(BULLETS) == "":
        i += 1
    if i < len(toks) and OPT_RE.match(toks[i][0].lstrip(BULLETS)):
        # glued letter (e.g. 'b)In') -> still skip just that token's letter influence
        rest = toks[i + 1:]
        if rest:
            return sum(c for _, c in rest) / len(rest)
        return toks[i][1]
    rest = toks[i:]
    return sum(c for _, c in rest) / len(rest) if rest else 0.0


def best_line(opt_words, lines):
    """Find line with max word-overlap vs the option's first words."""
    if not opt_words:
        return None, 0.0
    head = set(opt_words[:6])
    best, bestscore = None, 0.0
    for ln in lines:
        lw = set(ln["nw"][:8])
        if not lw:
            continue
        score = len(head & lw) / len(head)
        if score > bestscore:
            best, bestscore = ln, score
    return best, bestscore


def main():
    doc = fitz.open(PDF)
    cache = {}

    def lines_for(p):
        if p not in cache:
            cache[p] = page_lines(doc, p - 1) if 1 <= p <= doc.page_count else []
        return cache[p]

    changed = 0
    total_opts = 0
    unmatched = 0
    for f in sorted(glob.glob("/tmp/extract/grileB-*.json")):
        data = json.load(open(f))
        p = data["page"]
        pool = lines_for(p) + lines_for(p + 1)
        for q in data.get("questions", []):
            new_correct = []
            for letter, text in q.get("options", {}).items():
                total_opts += 1
                ln, score = best_line(norm(text), pool)
                if not ln or score < 0.4:
                    unmatched += 1
                    # keep vision's verdict when we can't locate the line
                    if letter in q.get("correct_answers", []):
                        new_correct.append(letter)
                    continue
                if answer_cov(ln) >= HI:
                    new_correct.append(letter)
            old = sorted(q.get("correct_answers", []))
            new = sorted(new_correct)
            if old != new:
                changed += 1
                print(f"p{p} '{q['question'][:45]}' : {old} -> {new}")
            q["correct_answers"] = new
        json.dump(data, open(f, "w"), ensure_ascii=False, indent=1)
    doc.close()
    print(f"\noptions checked={total_opts} unmatched={unmatched} questions_changed={changed}")


if __name__ == "__main__":
    main()
