import { createClient, type SupabaseClient, type User } from '@supabase/supabase-js';

// Public, browser-safe credentials (the anon key is designed to be exposed;
// row-level security is what actually protects each user's data). Set these as
// PUBLIC_* env vars locally (web/.env) and in Vercel's project settings.
const url = import.meta.env.PUBLIC_SUPABASE_URL as string | undefined;
const anon = import.meta.env.PUBLIC_SUPABASE_ANON_KEY as string | undefined;

export const supabaseConfigured = Boolean(url && anon);

// A single browser client that persists the session in localStorage and picks
// up the auth token from the redirect URL after Google/magic-link sign-in.
// Null when env isn't set yet, so pages degrade gracefully instead of crashing.
export const supabase: SupabaseClient | null = supabaseConfigured
  ? createClient(url!, anon!, {
      auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
        // Implicit flow returns the token directly in the redirect URL hash, so
        // sign-in doesn't rely on a code_verifier stashed in storage — which
        // Safari's tracking protection can wipe during the OAuth round-trip
        // (the cause of "returns to sign-in" after Google).
        flowType: 'implicit',
      },
    })
  : null;

// Resolve the session reliably — even immediately after an OAuth/magic-link
// redirect, when the URL still holds a code Supabase hasn't exchanged yet.
// Reading getSession() too early there returns null and looks "signed out";
// instead we wait for the auth event. Calls `cb` once with the user (or null
// when definitively signed out / the exchange fails).
export function onceSession(cb: (user: User | null) => void): void {
  if (!supabase) { cb(null); return; }
  const pendingRedirect =
    /[?&]code=/.test(location.search) || location.hash.includes('access_token');
  let done = false;
  const finish = (u: User | null) => { if (!done) { done = true; cb(u); } };
  supabase.auth.onAuthStateChange((event, session) => {
    if (session) finish(session.user);
    else if (event === 'INITIAL_SESSION' && !pendingRedirect) finish(null);
  });
  // If we came back from a redirect but the exchange never completes, stop waiting.
  if (pendingRedirect) setTimeout(() => finish(null), 6000);
}

export type ReadingStatus = 'want' | 'reading' | 'done';

export const STATUS_LABELS: Record<ReadingStatus, string> = {
  want: 'Read later',
  reading: 'Reading',
  done: 'Done',
};
