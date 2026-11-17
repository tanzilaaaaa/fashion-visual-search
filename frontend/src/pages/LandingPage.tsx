import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, imageSrc } from "../api/client";
import type { ItemSummary } from "../api/types";
import {
  ArrowRightIcon,
  BoltIcon,
  BrainIcon,
  CameraIcon,
  FilterIcon,
  HangerIcon,
  LayersIcon,
  SearchIcon,
  ShieldIcon,
  SparkIcon,
  TextIcon,
} from "../components/Icons";
import { Logo } from "../components/Logo";
import { ThemeSwitcher } from "../components/ThemeSwitcher";
import { useAuth } from "../context/AuthContext";
import { useAsync } from "../hooks/useAsync";
import { altText, percent } from "../lib/format";

const DEMO_QUERIES = ["a red casual summer dress", "black oversized hoodie", "blue denim jacket", "pleated mini skirt", "white linen trousers"];

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!mq) return;
    setReduced(mq.matches);
    const on = () => setReduced(mq.matches);
    mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, []);
  return reduced;
}

/** Types demo queries into a fake search bar, one character at a time. */
function TypingDemo() {
  const reduced = usePrefersReducedMotion();
  const [qi, setQi] = useState(0);
  const [n, setN] = useState(0);
  const [deleting, setDeleting] = useState(false);
  const q = DEMO_QUERIES[qi]!;

  useEffect(() => {
    if (reduced) return;
    const done = !deleting && n === q.length;
    const empty = deleting && n === 0;
    const delay = done ? 1600 : empty ? 300 : deleting ? 28 : 55;
    const t = setTimeout(() => {
      if (done) setDeleting(true);
      else if (empty) {
        setDeleting(false);
        setQi((i) => (i + 1) % DEMO_QUERIES.length);
      } else setN((v) => v + (deleting ? -1 : 1));
    }, delay);
    return () => clearTimeout(t);
  }, [n, deleting, q, reduced]);

  const shown = reduced ? q : q.slice(0, n);
  return (
    <div className="glass flex items-center gap-3 rounded-2xl px-4 py-3.5 shadow-lift" aria-hidden="true">
      <SearchIcon className="shrink-0 text-ink-muted" />
      <span className="min-w-0 flex-1 truncate text-sm text-ink sm:text-base">
        {shown}
        <span className="ml-0.5 inline-block h-5 w-[2px] translate-y-1 animate-blink bg-accent" />
      </span>
      <span className="btn-primary hidden px-4 py-1.5 text-xs sm:inline-flex">Search</span>
    </div>
  );
}

function Mosaic() {
  const showcase = useAsync(() => api.showcase(12), []);
  const items: (ItemSummary | null)[] = showcase.data?.items.length ? showcase.data.items : Array.from({ length: 9 }, () => null);
  const cols = [0, 1, 2].map((c) => items.filter((_, i) => i % 3 === c).slice(0, 4));
  return (
    <div className="relative grid h-[26rem] grid-cols-3 gap-3 overflow-hidden sm:h-[32rem] [mask-image:linear-gradient(to_bottom,transparent,black_12%,black_88%,transparent)]">
      {cols.map((col, c) => (
        <div key={c} className={`flex flex-col gap-3 ${c === 1 ? "translate-y-10" : c === 2 ? "translate-y-4" : ""}`}>
          {col.map((it, i) => (
            <div
              key={it?.item_id ?? `ph-${c}-${i}`}
              className="card aspect-[3/4] overflow-hidden p-0 animate-float"
              style={{ animationDelay: `${(c * 4 + i) * 0.35}s`, animationDuration: `${6 + c}s` }}
            >
              {it ? (
                <img src={imageSrc(it.image_url)} alt={altText(it)} loading="lazy" className="h-full w-full bg-surface-2 object-cover" />
              ) : (
                <div className={`grid h-full place-items-center bg-surface-2 text-ink-muted ${showcase.loading ? "shimmer" : ""}`}>
                  {!showcase.loading && <HangerIcon width={28} height={28} />}
                </div>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function LandingNav() {
  const { allowed, user } = useAuth();
  return (
    <header className="glass sticky top-0 z-40 border-x-0 border-t-0">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4 sm:px-6">
        <Logo />
        <nav className="ml-6 hidden items-center gap-6 text-sm font-medium text-ink-soft md:flex" aria-label="Sections">
          <a href="#how" className="hover:text-ink">How it works</a>
          <a href="#features" className="hover:text-ink">Features</a>
          <a href="#results" className="hover:text-ink">Results</a>
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <ThemeSwitcher compact />
          {allowed && user ? (
            <Link to="/app" className="btn-primary">Open app <ArrowRightIcon width={16} height={16} /></Link>
          ) : (
            <>
              <Link to="/signin" className="btn hidden px-4 text-ink-soft hover:text-ink sm:inline-flex">Sign in</Link>
              <Link to="/signup" className="btn-primary px-4">Get started</Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

function Section({ id, eyebrow, title, intro, children }: { id: string; eyebrow: string; title: ReactNode; intro?: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20 py-20 sm:py-24" aria-labelledby={`${id}-title`}>
      <div className="mx-auto max-w-7xl px-4 sm:px-6">
        <p className="eyebrow">{eyebrow}</p>
        <h2 id={`${id}-title`} className="mt-3 max-w-3xl font-display text-3xl font-semibold tracking-tight text-ink sm:text-5xl">
          {title}
        </h2>
        {intro && <p className="mt-4 max-w-2xl text-lg text-ink-soft">{intro}</p>}
        <div className="mt-12">{children}</div>
      </div>
    </section>
  );
}

const STEPS = [
  { icon: TextIcon, title: "Describe or upload", text: "Type what you have in mind in plain words, or drop in a photo of something you liked." },
  { icon: BrainIcon, title: "CLIP understands it", text: "OpenAI's CLIP ViT-B/32, plus our fine-tuned adapter, maps your words or photo into a 512-d style space." },
  { icon: BoltIcon, title: "FAISS finds matches", text: "Exact cosine search over ~50,000 garment crops returns the closest pieces in milliseconds." },
];

const FEATURES = [
  { icon: SearchIcon, title: "Natural-language search", text: "“A flowy red summer dress” works. No tags, no exact product names." },
  { icon: CameraIcon, title: "Search by photo", text: "Upload a street photo and find the shop items that look the same." },
  { icon: FilterIcon, title: "Smart filters", text: "Narrow by category, colour, photo type and viewpoint, applied inside the vector index." },
  { icon: SparkIcon, title: "Find Similar", text: "Jump from any item to its nearest visual neighbours." },
  { icon: LayersIcon, title: "Complete the Look", text: "Get compatible pieces from other categories, with outfits worn together in real photos shown first." },
  { icon: BrainIcon, title: "Fine-tuned for fashion", text: "A contrastive adapter trained on DeepFashion2 consumer↔shop pairs, on top of a frozen CLIP backbone." },
];

const STACK = ["CLIP ViT-B/32", "PyTorch", "FAISS", "FastAPI", "React", "Tailwind CSS", "DeepFashion2", "Docker", "Hugging Face Spaces", "Vercel", "Kaggle GPU", "pytest · Vitest"];

function Results() {
  const report = useAsync(() => api.evaluation(), []);
  const ev = report.data?.evaluation;
  const pre = ev?.variants?.pretrained.consumer_to_shop?.["recall@10"];
  const ft = ev?.variants?.finetuned.consumer_to_shop?.["recall@10"];
  const r10 = ev?.consumer_to_shop.clip?.["recall@10"];
  const base10 = ev?.consumer_to_shop.category_baseline?.["recall@10"];
  const p10 = ev?.text_to_image.clip["precision@10"];

  const stats: { label: string; value: string; note: string }[] = ev
    ? [
        { label: "Garments indexed", value: ev.catalogue_items.toLocaleString(), note: "DeepFashion2 crops, category-balanced" },
        pre !== undefined && ft !== undefined
          ? { label: "Street→shop Recall@10", value: percent(ft, 1), note: `fine-tuned · ${percent(pre, 1)} with pretrained CLIP` }
          : { label: "Street→shop Recall@10", value: r10 !== undefined ? percent(r10, 1) : "—", note: base10 !== undefined ? `vs ${percent(base10, 1)} category baseline` : "held-out slice" },
        { label: "Text search Precision@10", value: p10 !== undefined ? percent(p10, 0) : "—", note: "natural phrasings incl. synonyms" },
        { label: "Held-out eval items", value: ev.eval_items.toLocaleString(), note: "never indexed, never tuned on" },
      ]
    : [];

  return (
    <Section
      id="results"
      eyebrow="Measured, not claimed"
      title={<>Evaluated on data the model <span className="text-gradient">never saw</span>.</>}
      intro="Every number comes from a held-out DeepFashion2 validation slice, compared against simple baselines. The full report, including the fine-tuning ablation, is on the Insights page."
    >
      {report.loading ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <div key={i} className="shimmer h-36 rounded-theme" />)}
        </div>
      ) : stats.length ? (
        <dl className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label} className="card p-6">
              <dt className="text-sm text-ink-muted">{s.label}</dt>
              <dd className="mt-2 font-display text-4xl font-semibold tracking-tight text-ink tabular-nums">{s.value}</dd>
              <dd className="mt-2 text-xs text-ink-muted">{s.note}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="card p-6 text-ink-soft">The evaluation report appears here once the search server is online.</p>
      )}
    </Section>
  );
}

export function LandingPage() {
  const { allowed, user } = useAuth();
  const primary = allowed && user ? { to: "/app", label: "Open the app" } : { to: "/signup", label: "Start searching, it's free" };

  return (
    <div className="relative overflow-x-clip">
      <LandingNav />
      <main id="main">
        {/* Hero */}
        <section className="relative">
          <div className="bg-mesh pointer-events-none absolute inset-0" aria-hidden="true" />
          <div className="bg-grid pointer-events-none absolute inset-0 opacity-60" aria-hidden="true" />
          <div className="relative mx-auto grid max-w-7xl items-center gap-12 px-4 pb-16 pt-14 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:pb-24 lg:pt-20">
            <div className="animate-fade-up">
              <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium text-ink-soft">
                <span className="h-1.5 w-1.5 rounded-full bg-accent" /> AI visual search · CLIP + FAISS
              </span>
              <h1 className="mt-6 font-display text-5xl font-semibold leading-[1.02] tracking-tight text-ink sm:text-6xl lg:text-7xl">
                Find the look,
                <br />
                <span className="text-gradient italic">not the keyword.</span>
              </h1>
              <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink-soft">
                Lookbook understands fashion the way you see it. Describe a piece in your own words or upload a photo,
                and get visually matching garments from a 50,000-item catalogue in milliseconds.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <Link to={primary.to} className="btn-primary px-6 py-3 text-base">
                  {primary.label} <ArrowRightIcon width={18} height={18} />
                </Link>
                <a href="#how" className="btn-ghost px-6 py-3 text-base">See how it works</a>
              </div>
              <div className="mt-10 max-w-lg">
                <TypingDemo />
              </div>
              <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-muted">
                <li className="inline-flex items-center gap-1.5"><ShieldIcon width={16} height={16} className="text-accent" /> Photos never stored</li>
                <li className="inline-flex items-center gap-1.5"><BoltIcon width={16} height={16} className="text-accent" /> Results in milliseconds</li>
                <li className="inline-flex items-center gap-1.5"><BrainIcon width={16} height={16} className="text-accent" /> Fine-tuned on DeepFashion2</li>
              </ul>
            </div>
            <div className="animate-fade-up" style={{ animationDelay: "0.15s" }}>
              <Mosaic />
            </div>
          </div>
        </section>

        {/* Marquee */}
        <div className="border-y border-line bg-surface/50 py-4" aria-hidden="true">
          <div className="flex w-max animate-marquee gap-10 whitespace-nowrap font-display text-lg text-ink-muted">
            {[...STACK, ...STACK].map((s, i) => (
              <span key={i} className="inline-flex items-center gap-10">
                {s} <span className="text-accent">✦</span>
              </span>
            ))}
          </div>
        </div>

        <Section id="how" eyebrow="How it works" title={<>From an idea to a match <span className="text-gradient">in three steps</span>.</>}>
          <ol className="grid gap-5 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <li key={s.title} className="card group relative p-7 transition hover:-translate-y-1 hover:shadow-lift">
                <span className="font-display text-6xl font-semibold text-accent/15 transition group-hover:text-accent/25">0{i + 1}</span>
                <span className="bg-gradient-accent absolute right-6 top-7 grid h-11 w-11 place-items-center rounded-2xl text-on-accent shadow-glow">
                  <s.icon width={20} height={20} />
                </span>
                <h3 className="mt-2 text-xl font-semibold text-ink">{s.title}</h3>
                <p className="mt-2 text-ink-soft">{s.text}</p>
              </li>
            ))}
          </ol>
        </Section>

        <div className="border-y border-line bg-surface/40">
          <Section
            id="features"
            eyebrow="Features"
            title="Everything a shopper actually needs."
            intro="Built to the project PRD: multimodal retrieval, filtering, re-ranking and recommendations, all in one fast, accessible interface."
          >
            <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map((f) => (
                <li key={f.title} className="card p-6 transition hover:-translate-y-1 hover:border-accent/40 hover:shadow-lift">
                  <span className="grid h-11 w-11 place-items-center rounded-2xl bg-accent-soft text-accent">
                    <f.icon width={20} height={20} />
                  </span>
                  <h3 className="mt-5 text-lg font-semibold text-ink">{f.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">{f.text}</p>
                </li>
              ))}
            </ul>
          </Section>
        </div>

        <Results />

        {/* CTA */}
        <section className="px-4 pb-24 sm:px-6">
          <div className="bg-gradient-accent relative mx-auto max-w-6xl overflow-hidden rounded-[calc(var(--radius)*2)] px-6 py-16 text-center text-on-accent shadow-glow sm:px-12">
            <div className="bg-grid pointer-events-none absolute inset-0 opacity-20" aria-hidden="true" />
            <h2 className="relative font-display text-3xl font-semibold tracking-tight sm:text-5xl">Ready to find your look?</h2>
            <p className="relative mx-auto mt-4 max-w-xl text-lg opacity-90">
              Create a free account and search 50,000 garments by words or by photo.
            </p>
            <Link to={primary.to} className="btn relative mt-8 bg-canvas px-7 py-3 text-base text-ink hover:opacity-90">
              {primary.label} <ArrowRightIcon width={18} height={18} />
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-10 text-sm text-ink-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <Logo />
          <p>OJT project · Polaris School of Technology · Tanzila Tahreem · Mentor: Chennaveer Jogur</p>
          <p>DeepFashion2 used under its academic research terms.</p>
        </div>
      </footer>
    </div>
  );
}
