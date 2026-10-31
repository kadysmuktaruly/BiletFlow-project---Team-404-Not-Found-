// Liveness probe for the Docker health check. Does not call the API.
export function GET() {
  return Response.json({ status: "ok" });
}
