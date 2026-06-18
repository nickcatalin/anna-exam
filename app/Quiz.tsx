"use client";

import { useEffect, useMemo, useState } from "react";

type Question = {
  test: string;
  question: string;
  options: Record<string, string>;
  // Backwards compatible: older data uses a single `correct_answer` string,
  // newer multi-answer data uses a `correct_answers` array.
  correct_answer?: string;
  correct_answers?: string[];
  type?: string;
  number?: number;
};

/** Normalize either schema to the list of correct option keys. */
function correctKeys(q: Question): string[] {
  if (q.correct_answers && q.correct_answers.length > 0) return q.correct_answers;
  if (q.correct_answer) return [q.correct_answer];
  return [];
}

function sameSet(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const sb = new Set(b);
  return a.every((x) => sb.has(x));
}

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export default function Quiz() {
  const [all, setAll] = useState<Question[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // session state
  const [order, setOrder] = useState<Question[]>([]);
  const [idx, setIdx] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [revealed, setRevealed] = useState(false);
  const [correctCount, setCorrectCount] = useState(0);
  const [answeredCount, setAnsweredCount] = useState(0);

  useEffect(() => {
    fetch("/exam.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: Question[]) => {
        setAll(data);
        setOrder(shuffle(data));
      })
      .catch((e) => setError(String(e)));
  }, []);

  function restart() {
    if (!all) return;
    setOrder(shuffle(all));
    setIdx(0);
    setSelected([]);
    setRevealed(false);
    setCorrectCount(0);
    setAnsweredCount(0);
  }

  const current = order[idx];
  const finished = order.length > 0 && idx >= order.length;

  // stable option letters for current question
  const optionKeys = useMemo(
    () => (current ? Object.keys(current.options) : []),
    [current],
  );
  const answers = useMemo(() => (current ? correctKeys(current) : []), [current]);
  const isMulti = answers.length > 1;

  function grade(picks: string[]) {
    setRevealed(true);
    setAnsweredCount((c) => c + 1);
    if (sameSet(picks, answers)) setCorrectCount((c) => c + 1);
  }

  function toggle(key: string) {
    if (revealed || !current) return;
    if (isMulti) {
      setSelected((s) =>
        s.includes(key) ? s.filter((k) => k !== key) : [...s, key],
      );
    } else {
      // single-answer: pick reveals immediately
      setSelected([key]);
      grade([key]);
    }
  }

  function confirm() {
    if (revealed || selected.length === 0) return;
    grade(selected);
  }

  function next() {
    setSelected([]);
    setRevealed(false);
    setIdx((i) => i + 1);
  }

  if (error) {
    return (
      <Shell>
        <div className="rounded-xl border border-wrong/30 bg-wrong-soft px-6 py-5 text-wrong">
          Nu am putut încărca întrebările: {error}
        </div>
      </Shell>
    );
  }

  if (!all || order.length === 0) {
    return (
      <Shell>
        <div className="flex items-center gap-3 text-muted">
          <Pulse />
          Se încarcă întrebările…
        </div>
      </Shell>
    );
  }

  if (finished) {
    const pct = Math.round((correctCount / order.length) * 100);
    return (
      <Shell>
        <div className="pop-in w-full rounded-2xl border border-line bg-surface p-8 text-center shadow-sm">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-accent-soft text-accent">
            <Cross />
          </div>
          <h2 className="text-2xl font-semibold tracking-tight">
            Examen terminat
          </h2>
          <p className="mt-2 text-muted">
            Ai răspuns corect la{" "}
            <span className="font-semibold text-foreground">
              {correctCount}
            </span>{" "}
            din {order.length} întrebări.
          </p>
          <div className="mx-auto mt-6 max-w-xs">
            <div className="mb-1 flex justify-between text-sm font-medium text-muted">
              <span>Scor</span>
              <span
                className={
                  pct >= 50 ? "text-correct" : "text-wrong"
                }
              >
                {pct}%
              </span>
            </div>
            <Bar value={correctCount} max={order.length} />
          </div>
          <button
            onClick={restart}
            className="mt-8 inline-flex items-center gap-2 rounded-full bg-accent px-6 py-3 font-medium text-white transition-colors hover:bg-accent-deep"
          >
            <Refresh />
            Reia examenul
          </button>
        </div>
      </Shell>
    );
  }

  const isRight = revealed && sameSet(selected, answers);

  return (
    <Shell>
      {/* progress header */}
      <div className="mb-6 w-full">
        <div className="mb-2 flex items-center justify-between text-sm font-medium text-muted">
          <span>
            Întrebarea {idx + 1} / {order.length}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full bg-correct" />
            {correctCount} corecte
            {answeredCount > 0 && (
              <span className="text-muted/70">
                · {Math.round((correctCount / answeredCount) * 100)}%
              </span>
            )}
          </span>
        </div>
        <Bar value={idx} max={order.length} />
      </div>

      <div className="pop-in w-full rounded-2xl border border-line bg-surface p-6 shadow-sm sm:p-8">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-block rounded-full bg-accent-soft px-3 py-1 text-xs font-semibold uppercase tracking-wide text-accent-deep">
            {current.test}
          </span>
          {isMulti && (
            <span className="inline-block rounded-full bg-line px-3 py-1 text-xs font-semibold uppercase tracking-wide text-muted">
              {answers.length} răspunsuri corecte
            </span>
          )}
        </div>
        <h2 className="mt-4 text-lg font-semibold leading-relaxed tracking-tight sm:text-xl">
          {current.question}
        </h2>

        <div className="mt-6 flex flex-col gap-3">
          {optionKeys.map((key) => {
            const isAnswer = answers.includes(key);
            const isPicked = selected.includes(key);

            let cls =
              "border-line bg-surface hover:border-accent hover:bg-accent-soft/40";
            if (revealed) {
              if (isAnswer)
                cls = "border-correct bg-correct-soft text-correct";
              else if (isPicked)
                cls = "border-wrong bg-wrong-soft text-wrong";
              else cls = "border-line bg-surface opacity-60";
            } else if (isPicked) {
              cls = "border-accent bg-accent-soft/60";
            }

            return (
              <button
                key={key}
                onClick={() => toggle(key)}
                disabled={revealed}
                className={`flex w-full items-start gap-3 rounded-xl border px-4 py-3 text-left transition-all ${cls} ${
                  revealed ? "cursor-default" : "cursor-pointer"
                }`}
              >
                <span
                  className={`mt-0.5 flex h-7 w-7 flex-none items-center justify-center font-bold uppercase ${
                    isMulti ? "rounded-md" : "rounded-lg"
                  } border text-sm ${
                    revealed && isAnswer
                      ? "border-correct bg-correct text-white"
                      : revealed && isPicked
                        ? "border-wrong bg-wrong text-white"
                        : isPicked
                          ? "border-accent bg-accent text-white"
                          : "border-line bg-background text-muted"
                  }`}
                >
                  {key}
                </span>
                <span className="flex-1 pt-0.5 leading-relaxed">
                  {current.options[key]}
                </span>
                {revealed && isAnswer && (
                  <Check className="mt-0.5 text-correct" />
                )}
                {revealed && isPicked && !isAnswer && (
                  <X className="mt-0.5 text-wrong" />
                )}
              </button>
            );
          })}
        </div>

        {/* multi-select: confirm before revealing */}
        {isMulti && !revealed && (
          <div className="mt-6 flex items-center justify-between gap-4">
            <p className="text-sm text-muted">
              Selectează toate răspunsurile corecte, apoi confirmă.
            </p>
            <button
              onClick={confirm}
              disabled={selected.length === 0}
              className="inline-flex flex-none items-center gap-2 rounded-full bg-accent px-5 py-2.5 font-medium text-white transition-colors hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-50"
            >
              Confirmă răspunsul
            </button>
          </div>
        )}

        {revealed && (
          <div className="pop-in mt-6 flex items-center justify-between gap-4">
            <p
              className={`text-sm font-medium ${
                isRight ? "text-correct" : "text-wrong"
              }`}
            >
              {isRight
                ? "Corect!"
                : `Greșit — răspuns${answers.length > 1 ? "uri" : ""} corect${
                    answers.length > 1 ? "e" : ""
                  }: ${answers.map((a) => a.toUpperCase()).join(", ")}.`}
            </p>
            <button
              onClick={next}
              className="inline-flex flex-none items-center gap-2 rounded-full bg-accent px-5 py-2.5 font-medium text-white transition-colors hover:bg-accent-deep"
            >
              {idx + 1 >= order.length ? "Vezi rezultatul" : "Următoarea"}
              <Arrow />
            </button>
          </div>
        )}
      </div>

      <button
        onClick={restart}
        className="mt-6 inline-flex items-center gap-2 text-sm font-medium text-muted transition-colors hover:text-accent"
      >
        <Refresh small />
        Amestecă și reia
      </button>
    </Shell>
  );
}

/* ---------- layout + icons ---------- */

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center px-4 py-10 sm:py-16">
      <header className="mb-8 flex w-full max-w-2xl items-center gap-3">
        <div className="flex h-11 w-11 flex-none items-center justify-center rounded-xl bg-accent text-white shadow-sm">
          <Cross />
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight">
            Anna · Practică Examen
          </h1>
          <p className="text-sm text-muted">Quiz medical de practică</p>
        </div>
      </header>
      <div className="ekg-line mb-8 max-w-2xl" />
      <main className="flex w-full max-w-2xl flex-1 flex-col items-center">
        {children}
      </main>
    </div>
  );
}

function Bar({ value, max }: { value: number; max: number }) {
  const pct = max === 0 ? 0 : Math.round((value / max) * 100);
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-line">
      <div
        className="h-full rounded-full bg-accent transition-all duration-300"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function Cross() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
      <path d="M10 2h4v6h6v4h-6v6h-4v-6H4V8h6V2z" />
    </svg>
  );
}

function Check({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function X({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}

function Arrow() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

function Refresh({ small = false }: { small?: boolean }) {
  const s = small ? 16 : 18;
  return (
    <svg
      width={s}
      height={s}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 12a9 9 0 1 1-2.64-6.36M21 3v6h-6" />
    </svg>
  );
}

function Pulse() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="text-accent"
    >
      <path d="M2 12h4l2 7 4-14 2 7h6" />
    </svg>
  );
}
