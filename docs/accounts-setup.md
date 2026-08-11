# Turning on user accounts + reading lists

The code is deployed but **dormant** — it stays invisible until the two
`PUBLIC_SUPABASE_*` env vars exist. Do these three parts once and it goes live.

---

## A. Supabase — database + login

1. **Create the table.** Supabase → **SQL Editor** → New query → paste the contents
   of [`supabase/reading_list.sql`](../supabase/reading_list.sql) → **Run**.
2. **Grab your keys.** Supabase → **Project Settings → API**:
   - **Project URL** → this is `PUBLIC_SUPABASE_URL`
   - **anon public** key → this is `PUBLIC_SUPABASE_ANON_KEY`
     (This is the *public* key — safe to expose. Do **not** use the service key here.)
3. **Enable email (magic link).** Auth → **Providers → Email** → make sure it's ON.
4. **Set the allowed URLs.** Auth → **URL Configuration**:
   - **Site URL:** `https://www.bioread.bio`
   - **Redirect URLs** — add both:
     - `https://www.bioread.bio/**`
     - `http://localhost:4321/**`

## B. Google sign-in (the "Continue with Google" button)

1. **Google Cloud Console** → create/select a project.
2. **APIs & Services → OAuth consent screen** → External → fill in app name +
   your email → Save. (Add your own email under "Test users" so you can log in.)
3. **APIs & Services → Credentials → Create credentials → OAuth client ID** →
   type **Web application**.
4. **Authorized redirect URI** — paste the callback Supabase shows you under
   Auth → Providers → Google. It looks like:
   `https://<your-project-ref>.supabase.co/auth/v1/callback`
5. Copy the **Client ID** and **Client secret**, then in Supabase → Auth →
   **Providers → Google** → enable it and paste both. Save.

## C. Add the keys so the site can use them

1. **Vercel** → your project → **Settings → Environment Variables** → add:
   - `PUBLIC_SUPABASE_URL` = your Project URL
   - `PUBLIC_SUPABASE_ANON_KEY` = your anon public key

   Apply to **Production** (and Preview if you want). Then **Redeploy**.
2. **Local dev** (optional) — create `web/.env` with the same two lines so
   `npm run dev` works.

---

Once C is deployed, a **Sign in** link appears in the header, papers get a
**Read later / Reading / Done** control, and a **My Library** page collects each
user's saved papers — all private per account via row-level security.
