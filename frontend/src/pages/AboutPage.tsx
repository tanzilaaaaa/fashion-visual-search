import { api } from "../api/client";
import { DistributionBars, GroupedBars } from "../components/Charts";
import { useAsync } from "../hooks/useAsync";
import { formatBytes, humanise, percent } from "../lib/format";

const PIPELINE = [
  ["DeepFashion2", "Images + item annotations (category, bounding box, viewpoint, occlusion, consumer/shop pairs)."],
  ["Crop", "Each garment is cut from its bounding box with OpenCV, so one vector = one garment."],
  ["CLIP ViT-B/32", "Pretrained OpenAI weights encode every crop into a 512-d vector; text queries land in the same space."],
  ["FAISS", "Exact cosine search (IndexFlatIP over unit vectors), filtered with ID selectors."],
  ["Rank", "Final = α·similarity + β·attribute match, then Find Similar and Complete the Look."],
];

export function AboutPage() {
  const report = useAsync(() => api.evaluation(), []);
  const ev = report.data?.evaluation;
  const manifest = report.data?.manifest;

  return (
    <div className="mx-auto max-w-5xl px-4 pb-20 sm:px-6">
      <section className="py-10">
        <p className="text-sm font-medium uppercase tracking-wide text-accent">About this project</p>
        <h1 className="mt-1 font-display text-3xl font-semibold tracking-tight sm:text-4xl">AI-Powered Fashion Visual Search</h1>
        <p className="mt-3 max-w-3xl text-ink-soft">
          A multimodal search and recommendation engine. Shoppers rarely know a catalogue's tags — they know what an item looks
          like. Text and photos are embedded with CLIP into one vector space alongside the catalogue, so relevance becomes a
          similarity computation instead of a keyword match.
        </p>
        <p className="mt-3 text-sm text-ink-muted">
          OJT project · Polaris School of Technology · Tanzila Tahreem (ms240410700021) · Mentor: Chennaveer Jogur
        </p>
      </section>

      <section aria-labelledby="how">
        <h2 id="how" className="font-display text-2xl font-semibold">How it works</h2>
        <ol className="mt-5 grid gap-3 md:grid-cols-5">
          {PIPELINE.map(([title, text], i) => (
            <li key={title} className="rounded-xl border border-stone-200 bg-white p-4 shadow-card">
              <span className="text-xs font-semibold tabular-nums text-accent">0{i + 1}</span>
              <p className="mt-1 font-semibold">{title}</p>
              <p className="mt-1 text-xs leading-relaxed text-ink-muted">{text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section className="mt-14" aria-labelledby="eval">
        <h2 id="eval" className="font-display text-2xl font-semibold">Evaluation</h2>
        <p className="mt-1 text-sm text-ink-muted">
          Measured offline on a held-out DeepFashion2 validation slice that was never indexed or used for tuning.
        </p>

        {report.loading && <div className="mt-6 h-48 animate-pulse rounded-2xl bg-stone-200" />}
        {report.error && (
          <p className="mt-6 rounded-xl border border-stone-200 bg-white p-5 text-sm text-ink-muted">
            No evaluation report is available for the deployed index yet.
          </p>
        )}

        {ev && manifest && (
          <>
            <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Stat label="Items indexed" value={ev.catalogue_items.toLocaleString()} />
              <Stat label="Held-out eval items" value={ev.eval_items.toLocaleString()} />
              <Stat label="Recall@10 (consumer→shop)" value={ev.consumer_to_shop.clip ? percent(ev.consumer_to_shop.clip["recall@10"], 1) : "—"} />
              <Stat label="Index size" value={formatBytes(ev.footprint.index_bytes)} />
            </dl>

            <div className="mt-8 grid gap-6 md:grid-cols-2">
              {ev.consumer_to_shop.clip && ev.consumer_to_shop.category_baseline && (
                <Card
                  title="Street photo → shop item, Recall@K"
                  note={`${ev.consumer_to_shop.queries.toLocaleString()} consumer queries against ${ev.consumer_to_shop.gallery.toLocaleString()} shop items. A hit = the exact same garment (pair + style) is in the top K.`}
                >
                  <GroupedBars
                    clipLabel="CLIP embeddings"
                    baselineLabel="Same-category baseline"
                    rows={[1, 5, 10].map((k) => ({
                      label: `Recall@${k}`,
                      clip: ev.consumer_to_shop.clip![`recall@${k}`],
                      baseline: ev.consumer_to_shop.category_baseline![`recall@${k}`],
                    }))}
                  />
                </Card>
              )}
              <Card
                title="Text query → right category, Precision@K"
                note="Natural phrasings incl. synonyms (“blue jeans”, “tank top”) vs. a keyword baseline that matches query words to category names."
              >
                <GroupedBars
                  clipLabel="CLIP text search"
                  baselineLabel="Keyword baseline"
                  rows={[1, 5, 10].map((k) => ({
                    label: `P@${k}`,
                    clip: ev.text_to_image.clip[`precision@${k}`] ?? 0,
                    baseline: ev.text_to_image.keyword_baseline[`precision@${k}`] ?? 0,
                  }))}
                />
              </Card>
            </div>

            <details className="mt-6 rounded-xl border border-stone-200 bg-white p-4">
              <summary className="cursor-pointer text-sm font-semibold">Per-query table (text search)</summary>
              <table className="mt-3 w-full text-left text-sm">
                <caption className="sr-only">Precision at 10 for each probe query</caption>
                <thead className="text-xs uppercase tracking-wide text-ink-muted">
                  <tr><th className="py-1.5 font-medium">Query</th><th className="py-1.5 text-right font-medium">CLIP P@10</th><th className="py-1.5 text-right font-medium">Keyword P@10</th></tr>
                </thead>
                <tbody>
                  {ev.text_to_image.per_query.map((q) => (
                    <tr key={q.query} className="border-t border-stone-100">
                      <td className="py-1.5">{q.query}</td>
                      <td className="py-1.5 text-right tabular-nums">{percent(q["clip_precision@10"])}</td>
                      <td className="py-1.5 text-right tabular-nums">{percent(q["keyword_precision@10"])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>

            {ev.complete_the_look["clip_hit@10"] !== null && (
              <p className="mt-6 text-sm text-ink-soft">
                <strong>Complete the Look:</strong> for garments photographed together, the partner piece appears in the top 10
                suggestions {percent(ev.complete_the_look["clip_hit@10"] ?? 0)} of the time vs.{" "}
                {percent(ev.complete_the_look["random_hit@10"] ?? 0)} for random picks from the same categories.{" "}
                <span className="text-ink-muted">{ev.complete_the_look.note}</span>
              </p>
            )}
          </>
        )}

        {manifest?.category_counts && (
          <Card title="Catalogue items by category" note={manifest.built_at ? `Index built ${manifest.built_at}.` : undefined} className="mt-8">
            <DistributionBars
              data={Object.entries(manifest.category_counts)
                .map(([k, v]) => ({ label: humanise(k), value: v }))
                .sort((a, b) => b.value - a.value)}
            />
          </Card>
        )}
      </section>

      <section className="mt-14 grid gap-6 text-sm text-ink-soft md:grid-cols-2">
        <div>
          <h2 className="font-display text-xl font-semibold text-ink">Model & data</h2>
          <ul className="mt-3 list-disc space-y-1.5 pl-5">
            <li>OpenAI CLIP ViT-B/32, pretrained, via open_clip — no fine-tuning.</li>
            <li>DeepFashion2: ~491k images, 801k garments, 13 categories. A category-balanced working subset is indexed.</li>
            <li>Colour is tagged zero-shot with CLIP; DeepFashion2 has no colour labels.</li>
            <li>DeepFashion2 has no shoes or bags, so outfits pair tops, bottoms, outerwear and dresses.</li>
          </ul>
        </div>
        <div>
          <h2 className="font-display text-xl font-semibold text-ink">Privacy & licensing</h2>
          <ul className="mt-3 list-disc space-y-1.5 pl-5">
            <li>Uploaded photos are processed in memory and never stored or logged.</li>
            <li>DeepFashion2 is used under its academic research terms; only derived garment thumbnails are served.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-stone-200 bg-white p-4 shadow-card">
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className="mt-1 font-display text-2xl font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

function Card({ title, note, children, className = "" }: { title: string; note?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-2xl border border-stone-200 bg-white p-5 shadow-card ${className}`}>
      <h3 className="font-semibold">{title}</h3>
      {note && <p className="mb-4 mt-1 text-xs leading-relaxed text-ink-muted">{note}</p>}
      {children}
    </section>
  );
}
