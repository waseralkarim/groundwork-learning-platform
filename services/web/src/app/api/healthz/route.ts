/**
 * Web container liveness.
 *
 * Answers for this process only. It deliberately does not check the API — if it
 * did, an API restart would restart every web replica too.
 */

export const dynamic = "force-dynamic";

export function GET(): Response {
  return Response.json({ status: "alive" });
}
