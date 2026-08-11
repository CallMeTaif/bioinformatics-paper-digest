import { createClient, type SupabaseClient } from '@supabase/supabase-js';

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
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
    })
  : null;

export type ReadingStatus = 'want' | 'reading' | 'done';

export const STATUS_LABELS: Record<ReadingStatus, string> = {
  want: 'Read later',
  reading: 'Reading',
  done: 'Done',
};
