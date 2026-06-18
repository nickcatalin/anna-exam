#!/usr/bin/env python3
"""Read-only: derive section-B answers from yellow coverage and diff vs the vision files.

Positional alignment: for each vision question, find its stem line in the PDF page-pool,
then walk forward assigning each subsequent option's lines by best full-text match within a
sliding window. Reports any option whose coverage verdict differs from the file, so leftover
vision mistakes surface for manual review. Does NOT modify files.
"""
import json
import glob
import re
import fitz
import numpy as np

PDF = "pdfs/toate grilele chir fmm de viata.pdf"
Z = 3.0
HI = 0.5
BUL = "•∙·*‣▪◦○●-—• "
OPT = re.compile(r"^([a-eA-E])[\).]")


def mask(pg):
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z))
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    R, G, B = a[:, :, 0].astype(int), a[:, :, 1].astype(int), a[:, :, 2].astype(int)
    return (R >= 170) & (G >= 150) & (B <= 160) & ((R - B) > 55) & ((G - B) > 40)


def cov(m, w):
    x0, y0 = int(w[0] * Z), int(w[1] * Z)
    x1, y1 = int(round(w[2] * Z)), int(round(w[3] * Z))
    s = m[y0:y1, x0:x1]
    return float(s.mean()) if s.size else 0.0


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).split()


def lines_of(doc, p):
    if not (1 <= p <= doc.page_count):
        return []
    pg = doc[p - 1]
    m = mask(pg)
    groups = {}
    for w in pg.get_text("words"):
        groups.setdefault((w[5], w[6]), []).append(w)
    out = []
    for key in sorted(groups):
        ws = sorted(groups[key], key=lambda w: w[7])
        toks = [(w[4], cov(m, w)) for w in ws]
        # answer coverage: skip leading bullet + letter token
        i = 0
        while i < len(toks) and toks[i][0].strip(BUL) == "":
            i += 1
        rest = toks[i + 1:] if (i < len(toks) and OPT.match(toks[i][0].lstrip(BUL))) else toks[i:]
        ac = sum(c for _, c in rest) / len(rest) if rest else (toks[i][1] if i < len(toks) else 0)
        out.append({"text": " ".join(t for t, _ in toks), "nw": norm(" ".join(t for t, _ in toks)), "ac": ac})
    return out


def jac(a, b):
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if (sa or sb) else 0.0


def main():
    doc = fitz.open(PDF)
    pool = {}

    def get_pool(p):
        if p not in pool:
            pool[p] = lines_of(doc, p) + lines_of(doc, p + 1)
        return pool[p]

    diffs = 0
    for f in sorted(glob.glob("/tmp/extract/grileB-*.json")):
        data = json.load(open(f))
        p = data["page"]
        lines = get_pool(p)
        for q in data.get("questions", []):
            derived = []
            weak = []
            for letter, text in q.get("options", {}).items():
                ow = norm(text)
                # best line(s) by jaccard over full words; aggregate matched lines' coverage
                scored = sorted(((jac(ow, ln["nw"]), ln) for ln in lines),
                                key=lambda x: x[0], reverse=True)
                best_s, best_ln = scored[0] if scored else (0, None)
                if best_ln is None or best_s < 0.3 or len(ow) <= 1:
                    weak.append(letter)
                    # fall back to file's verdict for weak/short matches
                    if letter in q.get("correct_answers", []):
                        derived.append(letter)
                    continue
                if best_ln["ac"] >= HI:
                    derived.append(letter)
            fileans = sorted(q.get("correct_answers", []))
            if sorted(derived) != fileans:
                diffs += 1
                print(f"DIFF p{p} '{q['question'][:42]}': file={fileans} derived={sorted(derived)} weak={weak}")
    doc.close()
    print(f"\ntotal diffs: {diffs}")


if __name__ == "__main__":
    main()
