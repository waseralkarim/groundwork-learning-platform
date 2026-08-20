import { cookies } from "next/headers";

/**
 * Server-side session handling.
 *
 * The web service never inspects or validates the session token — it forwards
 * the cookie and lets the API decide. That keeps every authorisation decision
 * in one place, which is the only way to be sure there is not a second, weaker
 * copy of the rules somewhere.
 */

export const SESSION_COOKIE = "gw_session";

export async function sessionHeader(): Promise<Record<string, string>> {
  const store = await cookies();
  const token = store.get(SESSION_COOKIE)?.value;
  return token ? { cookie: `${SESSION_COOKIE}=${token}` } : {};
}

export async function isSignedIn(): Promise<boolean> {
  const store = await cookies();
  return Boolean(store.get(SESSION_COOKIE)?.value);
}
