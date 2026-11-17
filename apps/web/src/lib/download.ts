import { ApiError } from "./api";

/**
 * Save a file the API returned as a Blob. Downloads go through the typed client (so the
 * in-memory access token is sent), not a plain link, which couldn't carry the token.
 */
export async function saveDownload(
  call: Promise<{ data?: unknown; response: Response }>,
  filename: string,
): Promise<void> {
  let result: { data?: unknown; response: Response };
  try {
    result = await call;
  } catch {
    throw new ApiError("network");
  }
  if (!result.response.ok || !(result.data instanceof Blob)) throw new ApiError("download_failed");
  const url = URL.createObjectURL(result.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Give the browser a moment to start the download before releasing the object URL.
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
