import type { ReactNode } from "react";
import { api } from "../api/client";
import type { EvaluationReport, FinetuneReport } from "../api/types";
import { DistributionBars, GroupedBars, LineChart } from "../components/Charts";
import { useAsync } from "../hooks/useAsync";
import { formatBytes, humanise, percent } from "../lib/format";

const PIPELINE = [
  ["DeepFashion2", "491k photos, 801k garments with category, box, viewpoint, occlusion and consumer↔shop pair labels."],
  ["Crop", "Each garment is cut from its bounding box with OpenCV, so one vector describes one garment."],
  ["CLIP ViT-B/32", "Frozen OpenAI weights encode every crop into a 512-d vector; text lands in the same space."],
  ["Fine-tune", "A residual adapter is trained on consumer↔shop pairs with a contrastive loss + text alignment."],
  ["FAISS", "Exact cosine search (IndexFlatIP over unit vectors), filtered inside the index with ID selectors."],
  ["Rank", "Final = α·similarity + β·attribute match, then Find Similar and Complete the Look."],
];

type Ev = NonNullable<EvaluationReport["evaluation"]>;

const isFinetune = (f: Ev["finetune"]): f is FinetuneReport => !!f && "history" in f;

export function AboutPage() {
  const report = useAsync(() => api.evaluation(), []);
  const ev = report.data?.evaluation;
  const manifest = report.data?.manifest;
  const ft = isFinetune(ev?.finetune) ? ev!.finetune : null;

  return (
    <div className="mx-auto max-w-6xl px-4 pb-20 sm:px-6">
      <section className="py-10 sm:py-14">
        <p className="eyebrow">Model insights</p>
        <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight text-ink sm:text-5xl">
          How well does it <span className="text-gradient italic">see</span>?
        </h1>
        <p className="mt-4 max-w-3xl text-ink-soft">
          Shoppers rarely know a catalogue's tags; they know what an item looks like. Text and photos are embedded with CLIP
          into one vector space alongside the catalogue, so relevance becomes a similarity computation instead of a keyword
          match. Every number below is measured on a held-out DeepFashion2 slice that was never indexed or tuned on.
        </p>
        <p className="mt-3 text-sm text-ink-muted">
          OJT project · Polaris School of Technology · Tanzila Tahreem (ms240410700021) · Mentor: Chennaveer Jogur
        </p>
      </section>

      <section aria-labelledby="how">
        <h2 id="how" className="font-display text-2xl font-semibold text-ink">The pipeline</h2>
        <ol className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          {PIPELINE.map(([title, text], i) => (
            <li key={title} className="card p-4">
              <span className="text-xs font-semibold tabular-nums text-accent">0{i + 1}</span>
              <p className="mt-1 font-semibold text-ink">{title}</p>
              <p className="mt-1 text-xs leading-relaxed text-ink-muted">{text}</p>
            </li>
          ))}
        </ol>
      </section>

      {report.loading && <div className="shimmer mt-10 h-48 rounded-theme" />}
      {report.error && (
        <p className="card mt-10 p-5 text-sm text-ink-muted">No evaluation report is available for the deployed index yet.</p>
      )}

      {ev && manifest && (
        <>
          <dl className="mt-12 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Items indexed" value={ev.catalogue_items.toLocaleString()} />
            <Stat label="Held-out eval items" value={ev.eval_items.toLocaleString()} />
            <Stat label="Recall@10 (street→shop)" value={ev.consumer_to_shop.clip ? percent(ev.consumer_to_shop.clip["recall@10"], 1) : "—"} />
            <Stat label="Index size" value={formatBytes(ev.footprint.index_bytes)} />
          </dl>

          {ev.variants && <FinetuneSection ev={ev} ft={ft} />}
          {!ev.variants && ev.finetune && "skipped" in ev.finetune && (
            <p className="card mt-8 p-5 text-sm text-ink-muted">Fine-tuning was skipped for this build: {ev.finetune.skipped}</p>
          )}
          {!ev.variants && ft && (
            <p className="card mt-8 p-5 text-sm text-ink-muted">
              The adapter was trained, but the tuning split preferred r = 0 (pretrained CLIP), so the index serves pretrained vectors.
            </p>
          )}

          <section className="mt-14" aria-labelledby="baselines">
            <h2 id="baselines" className="font-display text-2xl font-semibold text-ink">Against simple baselines</h2>
            <p className="mt-1 text-sm text-ink-muted">What the served model achieves compared with what tags or keywords alone could do.</p>
            <div className="mt-6 grid gap-6 md:grid-cols-2">
              {ev.consumer_to_shop.clip && ev.consumer_to_shop.category_baseline && (
                <Card
                  title="Street photo → shop item, Recall@K"
                  note={`${ev.consumer_to_shop.queries.toLocaleString()} consumer queries against ${ev.consumer_to_shop.gallery.toLocaleString()} shop items. A hit = the exact same garment (pair + style) is in the top K.`}
                >
                  <GroupedBars
                    clipLabel="Lookbook embeddings"
                    baselineLabel="Same-category baseline"
                    rows={[1, 5, 10].map((k) => ({
                      label: `Recall@${k}`,
                      clip: ev.consumer_to_shop.clip![`recall@${k}`] ?? 0,
                      baseline: ev.consumer_to_shop.category_baseline![`recall@${k}`] ?? 0,
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

            <details className="card mt-6 p-4">
              <summary className="cursor-pointer text-sm font-semibold text-ink">Per-query table (text search)</summary>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Precision at 10 for each probe query</caption>
                  <thead className="text-xs uppercase tracking-wide text-ink-muted">
                    <tr><th className="py-1.5 font-medium">Query</th><th className="py-1.5 text-right font-medium">CLIP P@10</th><th className="py-1.5 text-right font-medium">Keyword P@10</th></tr>
                  </thead>
                  <tbody className="text-ink-soft">
                    {ev.text_to_image.per_query.map((q) => (
                      <tr key={q.query} className="border-t border-line">
                        <td className="py-1.5">{q.query}</td>
                        <td className="py-1.5 text-right tabular-nums">{percent(q["clip_precision@10"])}</td>
                        <td className="py-1.5 text-right tabular-nums">{percent(q["keyword_precision@10"])}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>

            {ev.complete_the_look["clip_hit@10"] !== null && (
              <p className="mt-6 text-sm text-ink-soft">
                <strong className="text-ink">Complete the Look:</strong> for garments photographed together, the partner piece
                appears in the top 10 suggestions {percent(ev.complete_the_look["clip_hit@10"] ?? 0)} of the time vs.{" "}
                {percent(ev.complete_the_look["random_hit@10"] ?? 0)} for random picks from the same categories.{" "}
                <span className="text-ink-muted">{ev.complete_the_look.note}</span>
              </p>
            )}
          </section>
        </>
      )}

      {manifest?.category_counts && (
        <Card title="Catalogue items by category" note={manifest.built_at ? `Index built ${manifest.built_at}.` : undefined} className="mt-10">
          <DistributionBars
            data={Object.entries(manifest.category_counts)
              .map(([k, v]) => ({ label: humanise(k), value: v }))
              .sort((a, b) => b.value - a.value)}
          />
        </Card>
      )}

      <section className="mt-14 grid gap-6 text-sm text-ink-soft md:grid-cols-2">
        <div className="card p-6">
          <h2 className="font-display text-xl font-semibold text-ink">Model & data</h2>
          <ul className="mt-3 list-disc space-y-1.5 pl-5">
            <li>OpenAI CLIP ViT-B/32 via open_clip. The backbone stays frozen.</li>
            <li>A 512→256→512 residual adapter, fine-tuned on DeepFashion2 consumer↔shop pairs (train split only).</li>
            <li>DeepFashion2: ~491k images, 801k garments, 13 categories. A category-balanced 50k working subset is indexed.</li>
            <li>Colour is tagged zero-shot with CLIP; DeepFashion2 has no colour labels.</li>
            <li>DeepFashion2 has no shoes or bags, so outfits pair tops, bottoms, outerwear and dresses.</li>
          </ul>
        </div>
        <div className="card p-6">
          <h2 className="font-display text-xl font-semibold text-ink">Privacy & licensing</h2>
          <ul className="mt-3 list-disc space-y-1.5 pl-5">
            <li>Uploaded photos are processed in memory and never stored or logged.</li>
            <li>Passwords are stored only as salted scrypt hashes; sessions use signed, expiring HttpOnly cookies.</li>
            <li>DeepFashion2 is used under its academic research terms; only derived garment thumbnails are served.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

function FinetuneSection({ ev, ft }: { ev: Ev; ft: FinetuneReport | null }) {
  const v = ev.variants!;
  const pre = v.pretrained.consumer_to_shop;
  const fin = v.finetuned.consumer_to_shop;
  const gain = pre && fin ? fin["recall@10"]! - pre["recall@10"]! : null;
  return (
    <section className="mt-14" aria-labelledby="finetune">
      <p className="eyebrow">Ablation</p>
      <h2 id="finetune" className="mt-2 font-display text-2xl font-semibold text-ink">Pretrained CLIP vs. fine-tuned adapter</h2>
      <p className="mt-1 max-w-3xl text-sm text-ink-muted">
        Same held-out slice, same index settings. The only difference is the adapter applied to image vectors.
        {gain !== null && (
          <>
            {" "}Street→shop Recall@10 changes by{" "}
            <strong className={gain >= 0 ? "text-success" : "text-danger"}>{gain >= 0 ? "+" : ""}{(gain * 100).toFixed(1)} points</strong>.
          </>
        )}
      </p>
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        {pre && fin && (
          <Card title="Street photo → shop item, Recall@K" note="Higher is better. The DeepFashion2 retrieval protocol (pair + style).">
            <GroupedBars
              clipLabel="Fine-tuned adapter"
              baselineLabel="Pretrained CLIP"
              rows={[1, 5, 10].map((k) => ({ label: `Recall@${k}`, clip: fin[`recall@${k}`] ?? 0, baseline: pre[`recall@${k}`] ?? 0 }))}
            />
          </Card>
        )}
        <Card
          title="Text query → right category, Precision@K"
          note={
            v.served
              ? "The adapter specialises the image space for photo matching and gives up some text alignment, so text queries are served from a second, pretrained-space index (dual index)."
              : "The trade-off: the adapter specialises the image space for photo→photo matching and gives up some text alignment."
          }
        >
          <GroupedBars
            clipLabel={v.served ? "Served: pretrained text index" : "Fine-tuned adapter"}
            baselineLabel={v.served ? "Adapter space only" : "Pretrained CLIP"}
            rows={[1, 5, 10].map((k) =>
              v.served
                ? { label: `P@${k}`, clip: v.served.text_to_image[`precision@${k}`] ?? 0, baseline: v.finetuned.text_to_image[`precision@${k}`] ?? 0 }
                : { label: `P@${k}`, clip: v.finetuned.text_to_image[`precision@${k}`] ?? 0, baseline: v.pretrained.text_to_image[`precision@${k}`] ?? 0 },
            )}
          />
        </Card>
      </div>

      {ft && (
        <div className="mt-6 grid gap-6 md:grid-cols-3">
          <Card title="Training loss" note="InfoNCE + λ·text-alignment, per epoch.">
            <LineChart
              label="Training loss"
              points={ft.history.filter((h) => h.loss !== null).map((h) => ({ x: h.epoch, y: h.loss! }))}
              format={(n) => n.toFixed(2)}
            />
          </Card>
          <Card title="Tuning-split Recall@10" note={`Best epoch ${ft.best_epoch} (marked) was kept.`}>
            <LineChart
              label="Tuning-split Recall@10"
              points={ft.history.map((h) => ({ x: h.epoch, y: h["val_recall@10"] }))}
              format={(n) => percent(n, 0)}
              highlight={ft.best_epoch}
            />
          </Card>
          <Card title="Training run" note={ft.method}>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <Mini label="Pair items" value={ft.pairs.items.toLocaleString()} />
              <Mini label="Groups (train)" value={ft.pairs.train_groups.toLocaleString()} />
              <Mini label="Chosen ratio r" value={ft.chosen_ratio.toFixed(1)} />
              <Mini label="Train time" value={`${Math.round(ft.train_seconds)} s on ${ft.device}`} />
            </dl>
            <table className="mt-4 w-full text-left text-xs">
              <caption className="sr-only">Residual ratio search on the tuning split</caption>
              <thead className="text-ink-muted">
                <tr><th className="py-1 font-medium">r</th><th className="py-1 text-right font-medium">R@10</th><th className="py-1 text-right font-medium">Text P@10</th></tr>
              </thead>
              <tbody className="text-ink-soft">
                {ft.ratio_search.map((r) => (
                  <tr key={r.ratio} className={`border-t border-line ${r.ratio === ft.chosen_ratio ? "font-semibold text-accent" : ""}`}>
                    <td className="py-1 tabular-nums">{r.ratio.toFixed(1)}</td>
                    <td className="py-1 text-right tabular-nums">{r["recall@10"] !== null ? percent(r["recall@10"], 1) : "—"}</td>
                    <td className="py-1 text-right tabular-nums">{percent(r["text_precision@10"], 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </div>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-5">
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className="mt-1 font-display text-3xl font-semibold tabular-nums text-ink">{value}</dd>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className="font-semibold tabular-nums text-ink">{value}</dd>
    </div>
  );
}

function Card({ title, note, children, className = "" }: { title: string; note?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`card p-5 ${className}`}>
      <h3 className="font-semibold text-ink">{title}</h3>
      {note && <p className="mb-4 mt-1 text-xs leading-relaxed text-ink-muted">{note}</p>}
      {children}
    </section>
  );
}
