// Client-side account glue: keeps the header's signed-in state in sync and wires
// up every reading-status control on the page. Imported once from Base.astro, so
// it runs on all pages. Safe no-op until Supabase env vars are configured.
import { supabase, type ReadingStatus } from './supabase';
import type { User } from '@supabase/supabase-js';

async function currentUser(): Promise<User | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.user ?? null;
}

function initHeader() {
  const slot = document.getElementById('auth-slot');
  if (!slot) return;
  const outEls = slot.querySelectorAll<HTMLElement>('[data-auth="out"]');
  const inEls = slot.querySelectorAll<HTMLElement>('[data-auth="in"]');
  const emailEl = slot.querySelector<HTMLElement>('[data-auth-email]');

  // The private Control Room link shows only for this account.
  const ADMIN_EMAIL = 'ai.taif.alharbi@gmail.com';
  const controlLink = document.getElementById('control-link');

  const render = (user: User | null) => {
    // Drives header links AND reveals reading-status controls (CSS: :root.has-user).
    document.documentElement.classList.toggle('has-user', !!user);
    outEls.forEach((e) => (e.hidden = !!user));
    inEls.forEach((e) => (e.hidden = !user));
    if (controlLink) controlLink.hidden = !(user && user.email?.toLowerCase() === ADMIN_EMAIL);
    if (emailEl && user) emailEl.textContent = user.email ?? 'Account';
  };
  render(null);
  if (!supabase) return;

  currentUser().then(render);
  supabase.auth.onAuthStateChange((_e, session) => render(session?.user ?? null));

  document.getElementById('logout')?.addEventListener('click', async () => {
    await supabase!.auth.signOut();
    location.href = '/';
  });
}

function paint(ctrl: HTMLElement, status: ReadingStatus | null) {
  ctrl.dataset.current = status ?? '';
  ctrl.querySelectorAll<HTMLButtonElement>('button[data-status]').forEach((b) => {
    b.classList.toggle('active', b.dataset.status === status);
  });
}

async function initReadingControls() {
  const controls = Array.from(document.querySelectorAll<HTMLElement>('.js-reading'));
  if (!controls.length || !supabase) return;

  const user = await currentUser();
  const byslug: Record<string, ReadingStatus> = {};
  if (user) {
    const slugs = controls.map((c) => c.dataset.slug!).filter(Boolean);
    const { data } = await supabase
      .from('reading_list')
      .select('paper_slug,status')
      .in('paper_slug', slugs);
    (data ?? []).forEach((r: any) => (byslug[r.paper_slug] = r.status));
  }

  for (const ctrl of controls) {
    const slug = ctrl.dataset.slug!;
    paint(ctrl, byslug[slug] ?? null);
    ctrl.querySelectorAll<HTMLButtonElement>('button[data-status]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!user) {
          location.href = '/login?next=' + encodeURIComponent(location.pathname);
          return;
        }
        const status = btn.dataset.status as ReadingStatus;
        const current = ctrl.dataset.current as ReadingStatus | '';
        if (current === status) {
          // Clicking the active status again clears it.
          await supabase!.from('reading_list').delete().eq('user_id', user.id).eq('paper_slug', slug);
          paint(ctrl, null);
        } else {
          await supabase!
            .from('reading_list')
            .upsert({ user_id: user.id, paper_slug: slug, status }, { onConflict: 'user_id,paper_slug' });
          paint(ctrl, status);
        }
      });
    });
  }
}

function boot() {
  initHeader();
  initReadingControls();
}
if (document.readyState !== 'loading') boot();
else document.addEventListener('DOMContentLoaded', boot);
