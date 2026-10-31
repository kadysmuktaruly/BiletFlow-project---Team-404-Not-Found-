/**
 * Types for the BiletFlow API, generated from its OpenAPI schema into `schema.d.ts`.
 * Regenerate with `npm run gen:api-types` from the repo root; never edit `schema.d.ts`.
 */
import type { components } from "./schema";

export type * from "./schema";

/** The one error body every non-2xx response uses. */
export type ApiErrorBody = components["schemas"]["ErrorResponse"];

/** Every request and response model, e.g. `Schemas["EventRead"]`. */
export type Schemas = components["schemas"];
