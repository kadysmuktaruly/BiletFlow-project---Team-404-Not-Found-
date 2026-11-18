/** The five check-in outcomes the door must show (SRS 4.8). */
export const RESULT_STATES = ["valid", "invalid", "cancelled", "refunded", "already_used"] as const;
export type ResultState = (typeof RESULT_STATES)[number];

export function isResultState(value: unknown): value is ResultState {
  return typeof value === "string" && (RESULT_STATES as readonly string[]).includes(value);
}

export type PayloadKind = "admission" | "campaign" | "unknown";

/**
 * A quick look at a scanned payload before asking the server. Admission tokens start with
 * `BFT1.`; Campaign QR codes carry a `BFC1.` token (often inside an https link). This never
 * decides that a ticket is valid: only the server, which checks the signature and the live
 * status, can do that.
 */
export function classifyPayload(payload: string): PayloadKind {
  const text = payload.trim();
  if (text.includes("BFC1.")) return "campaign";
  if (text.startsWith("BFT1.")) return "admission";
  return "unknown";
}

/**
 * Report 3 placeholder for the live check-in call (Report 4). Shapes look real but nothing is
 * recorded: admission-shaped payloads show "valid", everything else "invalid".
 */
export function mockResult(payload: string): ResultState {
  return classifyPayload(payload) === "admission" ? "valid" : "invalid";
}
