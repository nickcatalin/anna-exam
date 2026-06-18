#!/usr/bin/env python3
"""See PDF content: report structure, dump text layer, render pages to PNG.

Usage:
    python3 scripts/pdf_tool.py info  "pdfs/foo.pdf"
    python3 scripts/pdf_tool.py text  "pdfs/foo.pdf" [out.txt]
    python3 scripts/pdf_tool.py render "pdfs/foo.pdf" outdir [dpi]
"""
import sys
import os
import fitz  # PyMuPDF


def info(path):
    doc = fitz.open(path)
    print(f"file: {path}")
    print(f"pages: {doc.page_count}")
    for i, page in enumerate(doc):
        text = page.get_text("text")
        imgs = page.get_images(full=True)
        print(
            f"  p{i+1}: size={tuple(round(x) for x in page.rect.br)} "
            f"chars={len(text.strip())} images={len(imgs)}"
        )
    doc.close()


def text(path, out=None):
    doc = fitz.open(path)
    chunks = []
    for i, page in enumerate(doc):
        chunks.append(f"\n===== PAGE {i+1} =====\n")
        chunks.append(page.get_text("text"))
    doc.close()
    blob = "".join(chunks)
    if out:
        with open(out, "w") as f:
            f.write(blob)
        print(f"wrote {out} ({len(blob)} chars)")
    else:
        print(blob)


def render(path, outdir, dpi=170):
    os.makedirs(outdir, exist_ok=True)
    doc = fitz.open(path)
    n = doc.page_count
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=mat)
        fn = os.path.join(outdir, f"page-{i+1:03d}.png")
        pix.save(fn)
    doc.close()
    print(f"rendered {n} pages @ {dpi}dpi -> {outdir}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd, path = sys.argv[1], sys.argv[2]
    if cmd == "info":
        info(path)
    elif cmd == "text":
        text(path, sys.argv[3] if len(sys.argv) > 3 else None)
    elif cmd == "render":
        outdir = sys.argv[3] if len(sys.argv) > 3 else "render_out"
        dpi = int(sys.argv[4]) if len(sys.argv) > 4 else 170
        render(path, outdir, dpi)
    else:
        print(f"unknown cmd {cmd}")
        sys.exit(1)
