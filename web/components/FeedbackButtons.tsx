"use client";

import { useState } from "react";
import { sendFeedback } from "@/lib/api";

// 👍/👎 capture on an answer (F19). Optimistic: the choice sticks immediately; a
// thumbs-down opens an optional comment box to capture *why*.
export function FeedbackButtons({
  question,
  answer,
}: {
  question: string;
  answer: string;
}) {
  const [rating, setRating] = useState<"up" | "down" | null>(null);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState("");
  const [done, setDone] = useState(false);

  async function rate(value: "up" | "down") {
    if (rating) return;
    setRating(value);
    if (value === "down") {
      setShowComment(true);
      return;
    }
    await sendFeedback(question, answer, value).catch(() => {});
    setDone(true);
  }

  async function submitComment() {
    await sendFeedback(question, answer, "down", comment).catch(() => {});
    setShowComment(false);
    setDone(true);
  }

  return (
    <div className="mt-2 flex flex-col gap-2">
      <div className="flex items-center gap-2 text-sm muted">
        {done ? (
          <span>Thanks for the feedback.</span>
        ) : (
          <>
            <span>Helpful?</span>
            <button
              onClick={() => rate("up")}
              disabled={!!rating}
              className={`rounded-md px-1.5 py-0.5 transition hover:opacity-70 ${
                rating === "up" ? "text-emerald-500" : ""
              }`}
              aria-label="Helpful"
            >
              👍
            </button>
            <button
              onClick={() => rate("down")}
              disabled={rating === "up"}
              className={`rounded-md px-1.5 py-0.5 transition hover:opacity-70 ${
                rating === "down" ? "text-red-500" : ""
              }`}
              aria-label="Not helpful"
            >
              👎
            </button>
          </>
        )}
      </div>
      {showComment && (
        <div className="flex gap-2">
          <input
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="What was wrong? (optional)"
            className="surface flex-1 rounded-lg border px-2 py-1 text-sm focus:outline-none"
          />
          <button
            onClick={submitComment}
            className="rounded-lg bg-[var(--accent)] px-3 py-1 text-sm font-medium text-white"
          >
            Send
          </button>
        </div>
      )}
    </div>
  );
}
