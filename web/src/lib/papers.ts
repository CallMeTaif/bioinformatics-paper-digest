import data from '../data/papers.json';

export interface Summary {
  tldr: string;
  problem: string;
  methods: string;
  findings: string;
  why: string;
  limitations: string;
  takeaway: string;
  model?: string;
  provider?: string;
}

export interface Paper {
  slug: string;
  doi: string | null;
  title: string;
  authors: string[];
  venue: string | null;
  publication_date: string | null;
  source: string;
  is_preprint: boolean;
  oa_status: string | null;
  license: string;
  original_url: string | null;
  pdf_original_url: string | null;
  hosted_pdf_path: string | null;
  can_host: boolean;
  abstract: string | null;
  subfield_tags: string[];
  tag_accent: string | null;
  difficulty_level: 'intro' | 'intermediate' | 'advanced';
  summary: Summary;
  summary_provider: string;
  used_full_text: boolean;
  verifier_verdict?: 'pass' | 'flag' | null;
  verifier_score?: number | null;
  verifier_provider?: string | null;
  verifier_notes?: string | null;
  verifier_unsupported_claims?: string[] | null;
  status: string;
  date_posted?: string;
}

// True only when a real (non-mock) verifier checked this summary.
export function isVerified(p: Paper): boolean {
  return (
    !!p.verifier_provider &&
    p.verifier_provider !== 'mock' &&
    p.verifier_verdict === 'pass'
  );
}

const papers = data as unknown as Paper[];

export function allPapers(): Paper[] {
  return papers
    .filter((p) => p.status === 'published')
    .sort((a, b) => (b.date_posted ?? '').localeCompare(a.date_posted ?? ''));
}

export function getPaper(slug: string): Paper | undefined {
  return papers.find((p) => p.slug === slug);
}

// Ordered 7-section template for rendering the reading page.
export const SUMMARY_SECTIONS: { key: keyof Summary; label: string }[] = [
  { key: 'tldr', label: 'TL;DR' },
  { key: 'problem', label: 'Problem / question' },
  { key: 'methods', label: 'Methods' },
  { key: 'findings', label: 'Key findings' },
  { key: 'why', label: 'Why it matters' },
  { key: 'limitations', label: 'Limitations' },
  { key: 'takeaway', label: 'Takeaway' },
];

// Nucleotide accent -> CSS var (see global.css)
export function accentVar(accent: string | null): string {
  const map: Record<string, string> = { A: '--nt-a', C: '--nt-c', G: '--nt-g', T: '--nt-t' };
  return `var(${map[accent ?? 'A'] ?? '--nt-a'})`;
}

export function formatDate(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return isNaN(d.getTime()) ? '' : d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}
