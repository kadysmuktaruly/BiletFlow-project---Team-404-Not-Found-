import { useId } from "react";

// The shared building blocks of the BiletFlow design system (docs/design-direction.md).
// Tokens come from app/globals.css. Every input has a visible <label>, hints and errors are
// linked with aria-describedby, and errors are announced via role="alert".

const FIELD =
  "block w-full rounded-field border border-line-strong bg-surface px-3.5 text-ink transition-colors hover:border-ink-muted aria-invalid:border-danger aria-invalid:bg-danger-soft/40 disabled:cursor-not-allowed disabled:bg-paper disabled:text-ink-muted";
const LABEL = "mb-1.5 block text-sm font-semibold text-ink";
const HINT = "mt-1.5 text-sm text-ink-muted";

type FieldProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  hint?: string;
  error?: string;
};

export function Field({ label, hint, error, className, ...input }: FieldProps) {
  const id = useId();
  const describedBy = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ");
  return (
    <div className={className}>
      <label htmlFor={id} className={LABEL}>
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        className={`${FIELD} h-12 py-2`}
        {...input}
      />
      {hint && (
        <p id={`${id}-hint`} className={HINT}>
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-1.5 text-sm font-medium text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

type TextAreaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string };

export function TextArea({ label, className, ...input }: TextAreaProps) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className={LABEL}>
        {label}
      </label>
      <textarea id={id} rows={4} className={`${FIELD} py-3 leading-relaxed`} {...input} />
    </div>
  );
}

type SelectProps = React.SelectHTMLAttributes<HTMLSelectElement> & {
  label: string;
  hint?: string;
  options: { value: string; label: string }[];
};

export function Select({ label, hint, options, className, ...select }: SelectProps) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className={LABEL}>
        {label}
      </label>
      <select id={id} aria-describedby={hint ? `${id}-hint` : undefined} className={`${FIELD} h-12 py-2`} {...select}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {hint && (
        <p id={`${id}-hint`} className={HINT}>
          {hint}
        </p>
      )}
    </div>
  );
}

/** The compact select used inline (quantities, filters in a row): same look, smaller. */
export const INLINE_SELECT =
  "h-11 rounded-field border border-line-strong bg-surface px-3 text-sm font-semibold text-ink hover:border-ink-muted disabled:cursor-not-allowed disabled:bg-paper disabled:text-ink-muted";

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "md" | "sm";

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary: "bg-ink text-surface hover:bg-ink/85",
  secondary: "border border-line-strong bg-surface text-ink hover:border-ink hover:bg-paper",
  danger: "bg-danger text-surface hover:bg-danger/90",
  ghost: "text-ink underline-offset-4 hover:bg-ink/5 hover:underline",
};

const BUTTON_SIZES: Record<ButtonSize, string> = {
  md: "min-h-11 px-5 py-2.5 text-sm",
  sm: "min-h-9 px-3.5 py-1.5 text-sm",
};

/** Button styles, also for links that act as buttons. */
export function buttonClass(variant: ButtonVariant = "primary", size: ButtonSize = "md"): string {
  return `inline-flex items-center justify-center gap-2 rounded-full text-center font-semibold transition-[background-color,border-color,transform] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-50 disabled:active:scale-100 ${BUTTON_SIZES[size]} ${BUTTON_STYLES[variant]}`;
}

// React 19 passes `ref` as an ordinary prop, so it reaches the <button> through the spread.
type ButtonProps = React.ComponentProps<"button"> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
};

export function Button({ variant = "primary", size = "md", className = "", ...button }: ButtonProps) {
  return <button className={`${buttonClass(variant, size)} ${className}`} {...button} />;
}

/** A text link in body copy. */
export const LINK = "font-semibold text-sky-ink underline decoration-1 underline-offset-4 hover:decoration-2";

const ALERT_STYLES = {
  error: "border-danger/30 bg-danger-soft text-danger",
  success: "border-success/30 bg-success-soft text-success",
  info: "border-sky/40 bg-info-soft text-ink",
  demo: "border-ink bg-demo-soft text-ink",
};

export function Alert({
  kind = "info",
  children,
}: {
  kind?: keyof typeof ALERT_STYLES;
  children: React.ReactNode;
}) {
  return (
    <div
      role={kind === "error" ? "alert" : "status"}
      className={`rounded-card border px-4 py-3 text-sm leading-relaxed ${kind === "demo" ? "border-l-[6px]" : ""} ${ALERT_STYLES[kind]}`}
    >
      {children}
    </div>
  );
}

/** The DEMO marker required on every payment-related screen (SRS 4.6). Deliberately loud. */
export function DemoBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex shrink-0 items-center rounded-full border-2 border-ink bg-sun px-2.5 py-0.5 text-xs font-extrabold tracking-wide text-ink">
      {label}
    </span>
  );
}

export function PageTitle({ children, className = "mb-6" }: { children: React.ReactNode; className?: string }) {
  return <h1 className={`font-display text-title text-ink ${className}`}>{children}</h1>;
}

/** Section heading inside a page or card. */
export const SECTION_TITLE = "font-display text-xl text-ink";

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <section className={`rounded-card border border-line bg-surface p-5 sm:p-6 ${className}`}>{children}</section>;
}

const BADGE_TONES = {
  neutral: "bg-paper text-ink border-line",
  success: "bg-success-soft text-success border-success/30",
  info: "bg-info-soft text-sky-ink border-sky/40",
  warning: "bg-demo-soft text-ink border-sun",
  danger: "bg-danger-soft text-danger border-danger/30",
  promo: "bg-promo-soft text-promo border-promo/30",
  dark: "bg-ink text-surface border-ink",
};
export type BadgeTone = keyof typeof BADGE_TONES;

/** A status or category pill. The text always carries the meaning, colour only supports it. */
export function Badge({ tone = "neutral", children, className = "" }: { tone?: BadgeTone; children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[0.8125rem] font-semibold leading-5 ${BADGE_TONES[tone]} ${className}`}>
      {children}
    </span>
  );
}

/** A price in the display face. `size="lg"` for totals next to the main action. */
export function PriceTag({ children, size = "md", className = "" }: { children: React.ReactNode; size?: "md" | "lg"; className?: string }) {
  return (
    <span className={`font-display whitespace-nowrap text-ink tabular-nums ${size === "lg" ? "text-2xl" : "text-base"} ${className}`}>
      {children}
    </span>
  );
}

/** What a list shows when it has nothing in it: the message and, if the screen has one, its next step. */
export function EmptyState({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-card border-2 border-dashed border-line bg-surface/60 px-5 py-8 text-ink-muted">
      <div>{children}</div>
      {action}
    </div>
  );
}

/** A short confirmation next to the control that caused it ("Saved."). Announced politely. */
export function Toast({ children }: { children: React.ReactNode }) {
  return (
    <span role="status" className="inline-flex items-center gap-1.5 rounded-full bg-success-soft px-3 py-1 text-sm font-semibold text-success">
      <svg aria-hidden="true" viewBox="0 0 16 16" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M3 8.5 6.5 12 13 4.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {children}
    </span>
  );
}

/** A tab bar of pills that scrolls sideways on narrow screens instead of wrapping. */
export const TAB_BAR = "-mx-4 flex gap-1.5 overflow-x-auto px-4 pb-1 sm:mx-0 sm:flex-wrap sm:px-0";
export function tabClass(active: boolean): string {
  return `inline-flex min-h-10 shrink-0 items-center whitespace-nowrap rounded-full px-4 text-sm font-semibold transition-colors ${
    active ? "bg-ink text-surface" : "text-ink-muted hover:bg-surface hover:text-ink"
  }`;
}

/** Tables: hairline rows on a card. */
export const TABLE = "w-full text-left text-sm";
export const TH = "border-b border-line px-3 py-2.5 text-[0.8125rem] font-semibold text-ink-muted";
export const TD = "border-b border-line px-3 py-3 align-top";

/** The dialog surface (ConfirmDialog). It stays inline, so nothing is hidden behind an
 * overlay; the shadow and a short entrance show that it answers the click that opened it. */
export function modalClass(danger: boolean): string {
  return `space-y-3 rounded-card border-2 p-5 shadow-modal motion-safe:animate-[modal-in_160ms_ease-out] ${
    danger ? "border-danger bg-surface" : "border-ink bg-surface"
  }`;
}
