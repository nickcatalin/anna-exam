export const meta = {
  name: 'pdf-exam-extract',
  description: 'Vision-extract exam questions+answers from two medical PDFs',
  phases: [
    { title: 'Semio' },
    { title: 'GrileB' },
    { title: 'GrileAfix' },
    { title: 'Audit' },
  ],
}

const ROOT = '/Users/catalinnicola/Documents/projects/anna-exam'
const pad = (n) => String(n).padStart(3, '0')

const JSON_RULE =
  'Write ONLY raw JSON to the output file (no markdown fences, no prose). ' +
  'Use Romanian text exactly as written incl. original typos/diacritics. ' +
  'Keep your chat reply to one short line.'

function semioPrompt(p) {
  const img = `/tmp/semio/page-${pad(p)}.png`
  const txt = `/tmp/txt/semio-${pad(p)}.txt`
  const out = `/tmp/extract/semio-${pad(p)}.json`
  return `You extract ONE multiple-choice medical question from a quiz screenshot.

Read the image: ${img}
Read the OCR text layer (accurate wording): ${txt}

This page is exactly ONE question (quiz-screenshot style):
- A type header: "Complement Simplu (1 raspuns corect)" => exactly 1 correct answer;
  "Complement Multiplu (2, 3 sau 4 raspunsuri corecte)" => 2,3 or 4 correct answers.
- A numbered question stem (e.g. "26. ...").
- 4 or 5 answer options, each a statement with a CHECKBOX to its left. Options have NO
  letters — assign letters a,b,c,d,e top-to-bottom in order.

Determine the CORRECT options. An option is correct if EITHER:
  (1) its digital checkbox is CHECKED (filled blue box with a white check), OR
  (2) there is a HANDWRITTEN mark (blue/black pen: tick, check, X, circle, underline,
      arrow, line) pointing at / over that option.
Combine digital + handwritten marks (their UNION). If handwriting clearly crosses out a
digital check, exclude that option. Look carefully for faint handwriting in the margins.
SANITY CHECK against the header: simplu => exactly 1; multiplu => 2,3 or 4. If your count
violates this, re-examine the image (you likely missed a faint check or handwritten mark).

Use the OCR text for accurate option WORDING; use the IMAGE to decide which are marked.

Write to ${out} this exact JSON shape:
{"page":${p},"source":"semio","questions":[{
  "number": <int or null>,
  "type": "simplu" | "multiplu",
  "question": "<stem text>",
  "options": {"a":"...","b":"...","c":"...","d":"...","e":"..."},
  "correct_answers": ["a", ...],
  "confidence": "high" | "medium" | "low",
  "notes": "<how you decided; mention handwriting if any>"
}]}
${JSON_RULE}`
}

function grileBPrompt(p) {
  const img = `/tmp/grile/page-${pad(p)}.png`
  const txt = `/tmp/txt/grile-${pad(p)}.txt`
  const nxt = `/tmp/txt/grile-${pad(p + 1)}.txt`
  const nimg = `/tmp/grile/page-${pad(p + 1)}.png`
  const out = `/tmp/extract/grileB-${pad(p)}.json`
  return `You extract multiple-choice medical questions from a page with YELLOW HIGHLIGHTING.

Read the page image: ${img}
Read this page's text layer: ${txt}
Next page text (for options that spill over): ${nxt}
Next page image (only if a question's options continue there): ${nimg}

This page has 0-4 questions. A question = a stem sentence (often ending ":") followed by
~5 answer options. Options may be formatted as "a)" / "a." with letters, OR as bullet
points "•" with NO letters, OR as plain lines with no marker. If options have no letters,
assign a,b,c,d,e top-to-bottom in order.

CORRECT ANSWER RULE (critical): an option is correct ONLY if its ANSWER TEXT is highlighted
yellow essentially from start to end (most of the words highlighted). If only the bullet,
the letter, or just one or two words are highlighted, it is NOT correct. Multiple options
can be correct (2-4 typical); sometimes only 1.

PAGE-BOUNDARY RULES (avoid duplicates):
- Emit a question ONLY if its STEM begins on THIS page.
- If the page begins with options/bullets that have no stem above them on this page, those
  belong to the previous page's question — SKIP them.
- If a question's stem starts on this page but its options run onto the next page, include
  those options too (use next page text/image) and judge their highlight from the next image.

Write to ${out} this exact JSON shape:
{"page":${p},"source":"grileB","questions":[{
  "number": <int or null>,
  "question": "<stem text>",
  "options": {"a":"...","b":"...", ...},
  "correct_answers": ["a", ...],
  "confidence": "high" | "medium" | "low",
  "notes": "<note ambiguous highlights, spillover, etc>"
}]}
If the page has no question starting on it, write {"page":${p},"source":"grileB","questions":[]}.
${JSON_RULE}`
}

function grileAfixPrompt(p) {
  const img = `/tmp/grile/page-${pad(p)}.png`
  const txt = `/tmp/txt/grile-${pad(p)}.txt`
  const nxt = `/tmp/txt/grile-${pad(p + 1)}.txt`
  const nimg = `/tmp/grile/page-${pad(p + 1)}.png`
  const out = `/tmp/extract/grileAfix-${pad(p)}.json`
  return `You carefully re-extract ALL questions on one page of a highlighted medical exam.
An automated parser flagged this page as ambiguous (possible missing question number,
duplicate option letter, or borderline highlight). Resolve it from the image.

Read the page image: ${img}
Read this page's text layer (accurate wording): ${txt}
Next page text (for options that spill over): ${nxt}
Next page image (only if a question's options continue there): ${nimg}

Questions are numbered (e.g. "37."). Options are "a)"/"a." with letters a-e. NOTE: a
question's number may be MISSING in the text — if you see a fresh block of options a)-e)
with a stem but no number, it is still a separate question (set number to null). Watch for
DUPLICATE option letters (a source typo) — relabel them in correct a,b,c,d,e order.

CORRECT ANSWER RULE: an option is correct ONLY if its ANSWER TEXT is highlighted yellow
from start to end (most words highlighted), NOT just the letter. Multiple may be correct.

Emit every question whose stem begins on this page (skip option blocks continuing from the
previous page). If a question's stem starts on this page but its options continue on the
next page, INCLUDE those options (from the next page text/image) so the question is complete.
Write to ${out}:
{"page":${p},"source":"grileAfix","questions":[{
  "number": <int or null>,
  "question": "<stem>",
  "options": {"a":"...", ...},
  "correct_answers": ["a", ...],
  "confidence": "high" | "medium" | "low",
  "notes": "<what was wrong / how resolved>"
}]}
${JSON_RULE}`
}

function auditPrompt(p) {
  const img = `/tmp/grile/page-${pad(p)}.png`
  const nimg = `/tmp/grile/page-${pad(p + 1)}.png`
  const out = `/tmp/extract/audit-${pad(p)}.json`
  return `You AUDIT an automated highlight detector against the real page image.

Read the page image: ${img}
If a question's options run off the bottom of the page, also read the next page image to
verify those options: ${nimg}
Read the detector's claimed answers: /tmp/audit_hint.json  (use only the entry for page "${p}").

For each question on page ${p}, independently decide which options are correct using this
rule: an option is correct ONLY if its answer TEXT is highlighted yellow start-to-end (most
words), NOT just the letter/bullet. Check options that spill onto the next page using its
image. Then compare to the detector's correct_answers.

Write to ${out}:
{"page":${p},"source":"audit","results":[{
  "number": <int or null>,
  "detector_correct": ["a", ...],
  "vision_correct": ["a", ...],
  "match": <true|false>
}], "all_match": <true|false>, "notes":"<any disagreement explained>"}
${JSON_RULE}`
}

const SEMIO = Array.from({ length: 63 }, (_, i) => i + 1)
const GRILEB = Array.from({ length: 14 }, (_, i) => 66 + i) // pages 66..79
const GRILEAFIX = [10, 15, 18, 25, 29, 39, 65]
const AUDIT = [1, 7, 13, 19, 31, 37, 43, 49, 55, 61]

log(`semio=${SEMIO.length} grileB=${GRILEB.length} grileAfix=${GRILEAFIX.length} audit=${AUDIT.length}`)

const thunks = []
for (const p of SEMIO)
  thunks.push(() => agent(semioPrompt(p), { label: `semio p${p}`, phase: 'Semio' }))
for (const p of GRILEB)
  thunks.push(() => agent(grileBPrompt(p), { label: `grileB p${p}`, phase: 'GrileB' }))
for (const p of GRILEAFIX)
  thunks.push(() => agent(grileAfixPrompt(p), { label: `grileAfix p${p}`, phase: 'GrileAfix' }))
for (const p of AUDIT)
  thunks.push(() => agent(auditPrompt(p), { label: `audit p${p}`, phase: 'Audit' }))

const res = await parallel(thunks)
const ok = res.filter(Boolean).length
return { total: thunks.length, completed: ok, failed: thunks.length - ok }
