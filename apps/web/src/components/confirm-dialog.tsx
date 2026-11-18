"use client";

import { useEffect, useId, useRef } from "react";

import { Button, modalClass, TextArea } from "./ui";

/**
 * A confirmation step for actions that can't be undone (refunds, cancellations). It's an
 * `alertdialog`: focus moves into it when it opens, Escape closes it, and its title and text
 * are announced. Shown inline, so nothing is hidden behind an overlay.
 */
export function ConfirmDialog({
  title,
  text,
  confirmLabel,
  cancelLabel,
  reasonLabel,
  reasonRequired = false,
  busy,
  danger = true,
  onConfirm,
  onCancel,
}: {
  title: string;
  text: string;
  confirmLabel: string;
  cancelLabel: string;
  reasonLabel?: string;
  // The browser won't submit without a reason (at least 3 characters).
  reasonRequired?: boolean;
  busy?: boolean;
  danger?: boolean;
  onConfirm: (reason: string | null) => void;
  onCancel: () => void;
}) {
  const id = useId();
  const keep = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    // The safe choice gets focus first.
    keep.current?.focus();
  }, []);

  return (
    <form
      role="alertdialog"
      aria-labelledby={`${id}-title`}
      aria-describedby={`${id}-text`}
      className={modalClass(danger)}
      onKeyDown={(e) => {
        if (e.key === "Escape") onCancel();
      }}
      onSubmit={(e) => {
        e.preventDefault();
        const reason = String(new FormData(e.currentTarget).get("reason") ?? "").trim();
        onConfirm(reason || null);
      }}
    >
      <h3 id={`${id}-title`} className={`text-lg font-bold ${danger ? "text-danger" : "text-ink"}`}>
        {title}
      </h3>
      <p id={`${id}-text`} className="text-sm text-ink">
        {text}
      </p>
      {reasonLabel && (
        <TextArea
          name="reason"
          label={reasonLabel}
          rows={2}
          maxLength={2000}
          required={reasonRequired}
          minLength={reasonRequired ? 3 : undefined}
        />
      )}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant={danger ? "danger" : "primary"} disabled={busy}>
          {confirmLabel}
        </Button>
        <Button ref={keep} type="button" variant="secondary" onClick={onCancel}>
          {cancelLabel}
        </Button>
      </div>
    </form>
  );
}
