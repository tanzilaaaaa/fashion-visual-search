import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api, imageSrc, me, toApiError } from "../api/client";
import type { CollectionDetail, CollectionSummary, ItemSummary, ProfileResponse } from "../api/types";
import { Avatar, AVATAR_GRADIENTS } from "../components/Avatar";
import {
  ArrowLeftIcon,
  CheckIcon,
  ClockIcon,
  FolderIcon,
  GearIcon,
  HeartIcon,
  PinIcon,
  PlusIcon,
  SearchIcon,
  SparkIcon,
  TrashIcon,
  XIcon,
} from "../components/Icons";
import { ResultCard, ResultCardSkeleton, SaveButton } from "../components/ResultCard";
import { EmptyState, ErrorState } from "../components/States";
import { useAccount } from "../context/AccountContext";
import { useAuth } from "../context/AuthContext";
import { useSearch } from "../context/SearchContext";
import { useAsync } from "../hooks/useAsync";
import { altText, capitalise, COLOUR_SWATCH, humanise } from "../lib/format";
import { passwordProblem, passwordStrength } from "./AuthPage";

const TABS = [
  { id: "for-you", label: "For you", icon: SparkIcon },
  { id: "favorites", label: "Favorites", icon: HeartIcon },
  { id: "collections", label: "Collections", icon: FolderIcon },
  { id: "interests", label: "Interests", icon: PinIcon },
  { id: "history", label: "Recent searches", icon: ClockIcon },
  { id: "settings", label: "Settings", icon: GearIcon },
] as const;
type TabId = (typeof TABS)[number]["id"];

const memberSince = (ts: number) => new Date(ts * 1000).toLocaleDateString(undefined, { month: "long", year: "numeric" });

export function ProfilePage() {
  const { hash } = useLocation();
  const navigate = useNavigate();
  const tab: TabId = (TABS.find((t) => `#${t.id}` === hash)?.id ?? "for-you") as TabId;
  const profile = useAsync(() => me.profile(), []);
  const [data, setData] = useState<ProfileResponse | null>(null);
  useEffect(() => setData(profile.data), [profile.data]);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, []);

  if (profile.error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-16">
        <ErrorState error={profile.error} onRetry={profile.reload} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 pb-20 sm:px-6">
      <ProfileHeader data={data} />

      <nav className="-mx-4 mt-8 overflow-x-auto px-4 sm:mx-0 sm:px-0" aria-label="Profile sections">
        <ul className="flex min-w-max gap-1 rounded-full border border-line bg-surface/70 p-1">
          {TABS.map((t) => (
            <li key={t.id}>
              <button
                type="button"
                aria-current={tab === t.id ? "page" : undefined}
                onClick={() => navigate(`#${t.id}`, { replace: true })}
                className={`inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
                  tab === t.id ? "bg-ink text-canvas" : "text-ink-soft hover:bg-surface-2 hover:text-ink"
                }`}
              >
                <t.icon width={15} height={15} /> {t.label}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      <section className="mt-8" aria-live="polite">
        {tab === "for-you" && <ForYouTab goTo={(t) => navigate(`#${t}`, { replace: true })} />}
        {tab === "favorites" && <FavoritesTab onChange={profile.reload} />}
        {tab === "collections" && <CollectionsTab onChange={profile.reload} />}
        {tab === "interests" && data && <InterestsTab data={data} onSaved={(i) => setData({ ...data, interests: i })} />}
        {tab === "history" && <HistoryTab onChange={profile.reload} />}
        {tab === "settings" && data && <SettingsTab data={data} onUpdated={setData} />}
      </section>
    </div>
  );
}

// ------------------------------------------------------------------ header
function ProfileHeader({ data }: { data: ProfileResponse | null }) {
  const { user } = useAuth();
  const { avatarColor } = useAccount();
  const name = data?.user.name ?? user?.name ?? "";
  return (
    <section className="glass mt-8 flex flex-col gap-6 rounded-[calc(var(--radius)*1.5)] p-6 shadow-lift sm:flex-row sm:items-center sm:p-8">
      <div className="flex min-w-0 flex-1 items-center gap-5">
        <Avatar name={name} color={avatarColor ?? data?.profile.avatar_color} size={84} />
        <div className="min-w-0">
          <p className="eyebrow">Your profile</p>
          <h1 className="mt-1 break-words font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl">{name || " "}</h1>
          <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-muted">
            {data?.profile.location && (
              <span className="inline-flex items-center gap-1"><PinIcon width={14} height={14} /> {data.profile.location}</span>
            )}
            {data && <span>Member since {memberSince(data.member_since)}</span>}
          </p>
          {data?.profile.bio && <p className="mt-2 max-w-xl text-ink-soft">{data.profile.bio}</p>}
        </div>
      </div>
      <dl className="grid grid-cols-3 gap-3 sm:w-80">
        {([
          ["Favorites", data?.stats.favorites, "#favorites"],
          ["Collections", data?.stats.collections, "#collections"],
          ["Searches", data?.stats.searches, "#history"],
        ] as const).map(([label, value, href]) => (
          <a key={label} href={href} className="rounded-2xl border border-line bg-surface p-3 text-center transition hover:border-accent/50">
            <dd className="font-display text-2xl font-semibold tabular-nums text-ink">{value ?? "–"}</dd>
            <dt className="text-xs text-ink-muted">{label}</dt>
          </a>
        ))}
      </dl>
    </section>
  );
}

// ------------------------------------------------------------------ shared
function ItemTile({ item, footer }: { item: ItemSummary; footer?: ReactNode }) {
  return (
    <article className="card group flex h-full flex-col overflow-hidden p-0 transition hover:-translate-y-1 hover:shadow-lift">
      <div className="relative aspect-[3/4] overflow-hidden bg-surface-2">
        <Link to={`/app/item/${item.item_id}`} className="block h-full focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-accent">
          <img src={imageSrc(item.image_url)} alt={altText(item)} loading="lazy" className="h-full w-full object-contain p-3 transition duration-500 group-hover:scale-[1.05]" />
        </Link>
        <SaveButton itemId={item.item_id} label={altText(item)} className="absolute bottom-2.5 left-2.5" />
      </div>
      <div className="flex flex-1 flex-col gap-1 p-3.5">
        <h3 className="text-sm font-semibold text-ink">{capitalise(item.category)}</h3>
        <p className="inline-flex items-center gap-1 text-xs text-ink-muted">
          <span className="h-2.5 w-2.5 rounded-full border border-line" style={{ background: COLOUR_SWATCH[item.colour] ?? "#ccc" }} />
          {capitalise(item.colour)}
        </p>
        {footer}
      </div>
    </article>
  );
}

const GRID = "grid grid-cols-2 gap-4 sm:grid-cols-3 sm:gap-5 lg:grid-cols-4 xl:grid-cols-5";

function SkeletonGrid() {
  return (
    <div className={GRID} role="status" aria-label="Loading">
      {Array.from({ length: 5 }).map((_, i) => <ResultCardSkeleton key={i} />)}
    </div>
  );
}

function SectionTitle({ title, sub, action }: { title: string; sub?: string; action?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="font-display text-2xl font-semibold tracking-tight text-ink">{title}</h2>
        {sub && <p className="mt-1 text-sm text-ink-muted">{sub}</p>}
      </div>
      {action}
    </div>
  );
}

// ------------------------------------------------------------------ For you
function ForYouTab({ goTo }: { goTo: (t: TabId) => void }) {
  const recs = useAsync(() => me.recommendations(10), []);
  if (recs.error) return <ErrorState error={recs.error} onRetry={recs.reload} />;
  if (recs.loading || !recs.data) return <SkeletonGrid />;
  if (!recs.data.sections.length) {
    return (
      <EmptyState title="Your picks will appear here">
        Heart a few items you like, or tell us your interests, and Lookbook will recommend pieces in your style.
        <span className="mt-4 flex flex-wrap justify-center gap-2">
          <Link to="/app" className="btn-primary">Browse and save items</Link>
          <button type="button" className="btn-ghost" onClick={() => goTo("interests")}>Pick interests</button>
        </span>
      </EmptyState>
    );
  }
  return (
    <div className="space-y-12">
      {recs.data.sections.map((s) => (
        <div key={s.key}>
          <SectionTitle
            title={s.title}
            sub={s.key === "favorites" ? "Styled like the items you saved." : "Based on the colours, categories and styles you chose."}
            action={<button type="button" className="btn-ghost px-4 py-2" onClick={recs.reload}>Refresh</button>}
          />
          <ul className={GRID}>
            {s.items.map((it) => (
              <li key={it.item_id}><ResultCard item={it} showReason compact /></li>
            ))}
          </ul>
        </div>
      ))}
      {!recs.data.has_interests && (
        <p className="card p-5 text-sm text-ink-soft">
          Want sharper picks? <button type="button" className="font-semibold text-accent hover:underline" onClick={() => goTo("interests")}>Add your interests</button>.
        </p>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ Favorites
function FavoritesTab({ onChange }: { onChange: () => void }) {
  const favs = useAsync(() => me.favorites(), []);
  const { isFavorite } = useAccount();
  const [cat, setCat] = useState<string | null>(null);
  const items = useMemo(() => (favs.data?.items ?? []).filter((i) => isFavorite(i.item_id)), [favs.data, isFavorite]);
  const cats = useMemo(() => [...new Set(items.map((i) => i.category_key))].sort(), [items]);
  const shown = cat ? items.filter((i) => i.category_key === cat) : items;
  useEffect(() => {
    if (favs.data && items.length !== favs.data.items.length) onChange();
  }, [items.length]); // eslint-disable-line react-hooks/exhaustive-deps

  if (favs.error) return <ErrorState error={favs.error} onRetry={favs.reload} />;
  if (favs.loading) return <SkeletonGrid />;
  if (!items.length) {
    return (
      <EmptyState title="No favorites yet">
        Tap the heart on any item to save it here. <Link to="/app" className="font-medium text-accent underline">Start searching</Link>
      </EmptyState>
    );
  }
  return (
    <>
      <SectionTitle title="Favorites" sub={`${items.length} saved item${items.length === 1 ? "" : "s"}, newest first.`} />
      {cats.length > 1 && (
        <div className="mb-5 flex flex-wrap gap-2" role="group" aria-label="Filter favorites by category">
          <button type="button" aria-pressed={cat === null} className={`chip ${cat === null ? "border-accent text-accent" : ""}`} onClick={() => setCat(null)}>All</button>
          {cats.map((c) => (
            <button key={c} type="button" aria-pressed={cat === c} className={`chip ${cat === c ? "border-accent text-accent" : ""}`} onClick={() => setCat(c)}>
              {humanise(c)}
            </button>
          ))}
        </div>
      )}
      <ul className={GRID}>
        {shown.map((it) => (
          <li key={it.item_id}><ItemTile item={it} /></li>
        ))}
      </ul>
    </>
  );
}

// ------------------------------------------------------------------ Collections
function CollectionsTab({ onChange }: { onChange: () => void }) {
  const list = useAsync(() => me.collections(), []);
  const { notify } = useAccount();
  const [openId, setOpenId] = useState<number | null>(null);
  const [name, setName] = useState("");

  const create = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await me.createCollection(name.trim());
      setName("");
      list.reload();
      onChange();
      notify("Collection created");
    } catch (err) {
      notify(toApiError(err).message);
    }
  };

  if (openId !== null) {
    return <CollectionView id={openId} onBack={() => { setOpenId(null); list.reload(); onChange(); }} />;
  }
  return (
    <>
      <SectionTitle
        title="Collections"
        sub="Group your favorites into boards, like “Summer” or “Office”."
        action={
          <form onSubmit={create} className="flex gap-2">
            <label htmlFor="new-collection" className="sr-only">New collection name</label>
            <input id="new-collection" value={name} onChange={(e) => setName(e.target.value)} maxLength={40} placeholder="New collection" className="input w-48 py-2" />
            <button type="submit" className="btn-primary px-4"><PlusIcon width={16} height={16} /> Create</button>
          </form>
        }
      />
      {list.error && <ErrorState error={list.error} onRetry={list.reload} />}
      {list.loading && <SkeletonGrid />}
      {list.data && !list.data.collections.length && (
        <EmptyState title="No collections yet">Create one above, or use “Add to collection” on any item page.</EmptyState>
      )}
      {list.data && list.data.collections.length > 0 && (
        <ul className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {list.data.collections.map((c) => (
            <li key={c.id}><CollectionCard c={c} onOpen={() => setOpenId(c.id)} /></li>
          ))}
        </ul>
      )}
    </>
  );
}

function CollectionCard({ c, onOpen }: { c: CollectionSummary; onOpen: () => void }) {
  return (
    <button type="button" onClick={onOpen} className="card group w-full overflow-hidden p-0 text-left transition hover:-translate-y-1 hover:shadow-lift focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent">
      <div className="grid aspect-[4/3] grid-cols-2 grid-rows-2 gap-0.5 bg-line">
        {Array.from({ length: 4 }).map((_, i) => {
          const it = c.cover[i];
          return it ? (
            <img key={i} src={imageSrc(it.image_url)} alt="" loading="lazy" className="h-full w-full bg-surface-2 object-cover" />
          ) : (
            <span key={i} className="grid place-items-center bg-surface-2 text-ink-muted/40"><FolderIcon width={20} height={20} /></span>
          );
        })}
      </div>
      <div className="flex items-center justify-between p-4">
        <span className="min-w-0">
          <span className="block truncate font-semibold text-ink">{c.name}</span>
          <span className="text-xs text-ink-muted">{c.count} item{c.count === 1 ? "" : "s"}</span>
        </span>
        <span className="text-sm font-medium text-accent">Open</span>
      </div>
    </button>
  );
}

function CollectionView({ id, onBack }: { id: number; onBack: () => void }) {
  const [col, setCol] = useState<CollectionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { notify } = useAccount();

  useEffect(() => {
    me.collection(id).then((c) => { setCol(c); setName(c.name); }).catch((e) => setError(toApiError(e).message));
  }, [id]);

  const rename = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const c = await me.renameCollection(id, name.trim());
      setCol(c);
      setRenaming(false);
      notify("Collection renamed");
    } catch (err) {
      notify(toApiError(err).message);
    }
  };
  const remove = async (itemId: string) => {
    try {
      setCol(await me.removeFromCollection(id, itemId));
    } catch (err) {
      notify(toApiError(err).message);
    }
  };
  const destroy = async () => {
    try {
      await me.deleteCollection(id);
      notify("Collection deleted");
      onBack();
    } catch (err) {
      notify(toApiError(err).message);
    }
  };

  return (
    <>
      <button type="button" onClick={onBack} className="mb-4 inline-flex items-center gap-1.5 text-sm font-medium text-ink-soft hover:text-ink">
        <ArrowLeftIcon width={16} height={16} /> All collections
      </button>
      {error && <p className="card p-5 text-sm text-danger">{error}</p>}
      {col && (
        <>
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            {renaming ? (
              <form onSubmit={rename} className="flex gap-2">
                <label htmlFor="rename-col" className="sr-only">Collection name</label>
                <input id="rename-col" value={name} onChange={(e) => setName(e.target.value)} maxLength={40} className="input py-2" autoFocus />
                <button type="submit" className="btn-primary px-4">Save</button>
                <button type="button" className="btn-ghost px-4" onClick={() => setRenaming(false)}>Cancel</button>
              </form>
            ) : (
              <h2 className="font-display text-3xl font-semibold tracking-tight text-ink">
                {col.name} <span className="text-base font-normal text-ink-muted">· {col.count} item{col.count === 1 ? "" : "s"}</span>
              </h2>
            )}
            {!renaming && (
              <div className="flex flex-wrap gap-2">
                <button type="button" className="btn-ghost px-4 py-2" onClick={() => setRenaming(true)}>Rename</button>
                {confirmDelete ? (
                  <span className="flex items-center gap-2 rounded-full border border-danger/40 bg-danger-soft px-3 py-1 text-sm text-ink">
                    Delete “{col.name}”? Items stay in favorites.
                    <button type="button" className="font-semibold text-danger hover:underline" onClick={() => void destroy()}>Delete</button>
                    <button type="button" className="text-ink-muted hover:underline" onClick={() => setConfirmDelete(false)}>Keep</button>
                  </span>
                ) : (
                  <button type="button" className="btn-ghost px-4 py-2 text-danger" onClick={() => setConfirmDelete(true)}>
                    <TrashIcon width={15} height={15} /> Delete
                  </button>
                )}
              </div>
            )}
          </div>
          {col.items.length === 0 ? (
            <EmptyState title="This collection is empty">Open any item and choose “Add to collection”.</EmptyState>
          ) : (
            <ul className={GRID}>
              {col.items.map((it) => (
                <li key={it.item_id}>
                  <ItemTile
                    item={it}
                    footer={
                      <button type="button" onClick={() => void remove(it.item_id)} className="mt-2 inline-flex items-center gap-1 self-start text-xs font-medium text-ink-muted hover:text-danger">
                        <XIcon width={13} height={13} /> Remove from collection
                      </button>
                    }
                  />
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </>
  );
}

// ------------------------------------------------------------------ Interests
function ChipToggle({ on, onClick, children }: { on: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${
        on ? "border-accent bg-accent text-on-accent" : "border-line bg-surface text-ink-soft hover:border-accent"
      }`}
    >
      {on && <CheckIcon width={14} height={14} />}
      {children}
    </button>
  );
}

function InterestsTab({ data, onSaved }: { data: ProfileResponse; onSaved: (i: ProfileResponse["interests"]) => void }) {
  const vocab = useAsync(() => api.filters(), []);
  const { notify } = useAccount();
  const [cats, setCats] = useState(new Set(data.interests.categories));
  const [cols, setCols] = useState(new Set(data.interests.colours));
  const [styles, setStyles] = useState<string[]>(data.interests.styles);
  const [custom, setCustom] = useState("");
  const [saving, setSaving] = useState(false);

  const flip = (set: Set<string>, setter: (s: Set<string>) => void, v: string) => {
    const next = new Set(set);
    next.has(v) ? next.delete(v) : next.add(v);
    setter(next);
  };
  const toggleStyle = (s: string) => setStyles((prev) => (prev.includes(s) ? prev.filter((x) => x !== s) : [...prev, s].slice(0, 12)));
  const addCustom = (e: FormEvent) => {
    e.preventDefault();
    const s = custom.trim().toLowerCase();
    if (s && !styles.includes(s)) setStyles((prev) => [...prev, s].slice(0, 12));
    setCustom("");
  };
  const save = async () => {
    setSaving(true);
    try {
      const i = await me.setInterests({ categories: [...cats], colours: [...cols], styles });
      onSaved(i);
      notify("Interests saved. Your “For you” picks are updated.");
    } catch (err) {
      notify(toApiError(err).message);
    } finally {
      setSaving(false);
    }
  };

  const allStyles = [...new Set([...data.style_presets, ...styles])];
  return (
    <div className="space-y-8">
      <SectionTitle title="Your interests" sub="Pick what you like. Lookbook uses these for your “For you” recommendations." />
      <div className="card p-6">
        <h3 className="eyebrow mb-3">Categories</h3>
        <div className="flex flex-wrap gap-2">
          {vocab.data?.fields.category.options.map((o) => (
            <ChipToggle key={o.value} on={cats.has(o.value)} onClick={() => flip(cats, setCats, o.value)}>{o.label}</ChipToggle>
          )) ?? <span className="text-sm text-ink-muted">Loading…</span>}
        </div>
      </div>
      <div className="card p-6">
        <h3 className="eyebrow mb-3">Colours</h3>
        <div className="flex flex-wrap gap-2">
          {vocab.data?.fields.colour.options.filter((o) => o.value !== "multicolour").map((o) => (
            <ChipToggle key={o.value} on={cols.has(o.value)} onClick={() => flip(cols, setCols, o.value)}>
              <span className="h-3 w-3 rounded-full border border-line" style={{ background: COLOUR_SWATCH[o.value] ?? "#ccc" }} />
              {o.label}
            </ChipToggle>
          )) ?? <span className="text-sm text-ink-muted">Loading…</span>}
        </div>
      </div>
      <div className="card p-6">
        <h3 className="eyebrow mb-3">Styles</h3>
        <div className="flex flex-wrap gap-2">
          {allStyles.map((s) => (
            <ChipToggle key={s} on={styles.includes(s)} onClick={() => toggleStyle(s)}>{capitalise(s)}</ChipToggle>
          ))}
        </div>
        <form onSubmit={addCustom} className="mt-4 flex max-w-sm gap-2">
          <label htmlFor="custom-style" className="sr-only">Add your own style</label>
          <input id="custom-style" value={custom} onChange={(e) => setCustom(e.target.value)} maxLength={24} placeholder="Add your own, e.g. “denim”" className="input py-2" />
          <button type="submit" className="btn-ghost px-4">Add</button>
        </form>
      </div>
      <div className="flex justify-end">
        <button type="button" className="btn-primary px-6 py-3" disabled={saving} onClick={() => void save()}>
          {saving ? "Saving…" : "Save interests"}
        </button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ History
function HistoryTab({ onChange }: { onChange: () => void }) {
  const hist = useAsync(() => me.history(), []);
  const s = useSearch();
  const navigate = useNavigate();
  const { notify } = useAccount();

  const rerun = (q: string) => {
    navigate("/app");
    void s.searchText(q);
  };
  const remove = async (id: number) => {
    await me.deleteHistory(id).catch((e) => notify(toApiError(e).message));
    hist.reload();
    onChange();
  };
  const clear = async () => {
    await me.clearHistory().catch((e) => notify(toApiError(e).message));
    hist.reload();
    onChange();
    notify("Search history cleared");
  };

  if (hist.error) return <ErrorState error={hist.error} onRetry={hist.reload} />;
  if (hist.loading || !hist.data) return <div className="shimmer h-48 rounded-theme" />;
  if (!hist.data.entries.length) {
    return <EmptyState title="No searches yet">Your text searches are saved here, on any device you sign in from.</EmptyState>;
  }
  return (
    <>
      <SectionTitle
        title="Recent searches"
        sub="Saved to your account, so they follow you to any device. Photo searches are never stored."
        action={<button type="button" className="btn-ghost px-4 py-2" onClick={() => void clear()}><TrashIcon width={15} height={15} /> Clear all</button>}
      />
      <ul className="card divide-y divide-line p-0">
        {hist.data.entries.map((e) => (
          <li key={e.id} className="flex items-center gap-3 px-4 py-3">
            <SearchIcon width={16} height={16} className="shrink-0 text-ink-muted" />
            <button type="button" onClick={() => rerun(e.query)} className="min-w-0 flex-1 truncate text-left font-medium text-ink hover:text-accent">
              {e.query}
            </button>
            <span className="hidden text-xs text-ink-muted sm:inline">{new Date(e.created_at * 1000).toLocaleString()}</span>
            <button type="button" aria-label={`Remove “${e.query}” from history`} onClick={() => void remove(e.id)} className="rounded-full p-1.5 text-ink-muted hover:bg-surface-2 hover:text-danger">
              <XIcon width={15} height={15} />
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}

// ------------------------------------------------------------------ Settings
function SettingsTab({ data, onUpdated }: { data: ProfileResponse; onUpdated: (p: ProfileResponse) => void }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <ProfileForm data={data} onUpdated={onUpdated} />
      <div className="space-y-6">
        <EmailForm data={data} onUpdated={onUpdated} />
        <PasswordForm />
      </div>
      <DangerZone email={data.user.email} />
    </div>
  );
}

function Field({ id, label, children, hint }: { id: string; label: string; children: ReactNode; hint?: string }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-ink">{label}</label>
      {children}
      {hint && <p className="mt-1 text-xs text-ink-muted">{hint}</p>}
    </div>
  );
}

function ProfileForm({ data, onUpdated }: { data: ProfileResponse; onUpdated: (p: ProfileResponse) => void }) {
  const { notify, setAvatarColor } = useAccount();
  const [name, setName] = useState(data.user.name);
  const [bio, setBio] = useState(data.profile.bio);
  const [location, setLocation] = useState(data.profile.location);
  const [color, setColor] = useState(data.profile.avatar_color);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const p = await me.updateProfile({ name, bio, location, avatar_color: color });
      onUpdated(p);
      setAvatarColor(p.profile.avatar_color);
      notify("Profile saved");
    } catch (err) {
      notify(toApiError(err).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="card space-y-5 p-6 lg:row-span-2">
      <h2 className="font-display text-xl font-semibold text-ink">Profile</h2>
      <div className="flex items-center gap-4">
        <Avatar name={name || data.user.name} color={color} size={64} />
        <div role="radiogroup" aria-label="Avatar colour" className="flex flex-wrap gap-2">
          {data.avatar_colors.map((c) => {
            const [a, b] = AVATAR_GRADIENTS[c] ?? AVATAR_GRADIENTS.rose!;
            return (
              <button
                key={c}
                type="button"
                role="radio"
                aria-checked={color === c}
                aria-label={capitalise(c)}
                onClick={() => setColor(c)}
                className={`h-8 w-8 rounded-full transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent ${color === c ? "ring-2 ring-ink ring-offset-2 ring-offset-surface" : ""}`}
                style={{ background: `linear-gradient(135deg, ${a}, ${b})` }}
              />
            );
          })}
        </div>
      </div>
      <Field id="pf-name" label="Name">
        <input id="pf-name" value={name} onChange={(e) => setName(e.target.value)} maxLength={60} required className="input" autoComplete="name" />
      </Field>
      <Field id="pf-location" label="Location" hint="Optional, e.g. a city.">
        <input id="pf-location" value={location} onChange={(e) => setLocation(e.target.value)} maxLength={60} className="input" />
      </Field>
      <Field id="pf-bio" label="Bio" hint={`${bio.length}/280`}>
        <textarea id="pf-bio" value={bio} onChange={(e) => setBio(e.target.value)} maxLength={280} rows={3} className="input resize-none" placeholder="A line about your style" />
      </Field>
      <button type="submit" disabled={busy} className="btn-primary">{busy ? "Saving…" : "Save profile"}</button>
    </form>
  );
}

function EmailForm({ data, onUpdated }: { data: ProfileResponse; onUpdated: (p: ProfileResponse) => void }) {
  const { notify } = useAccount();
  const [email, setEmail] = useState(data.user.email);
  const [pw, setPw] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const u = await me.changeEmail(email.trim(), pw);
      onUpdated({ ...data, user: u });
      setPw("");
      notify("Email updated");
    } catch (err) {
      setError(toApiError(err).message);
    }
  };
  return (
    <form onSubmit={submit} className="card space-y-4 p-6">
      <h2 className="font-display text-xl font-semibold text-ink">Email</h2>
      <Field id="em-email" label="Email address">
        <input id="em-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="input" autoComplete="email" />
      </Field>
      <Field id="em-pw" label="Current password">
        <input id="em-pw" type="password" value={pw} onChange={(e) => setPw(e.target.value)} required className="input" autoComplete="current-password" />
      </Field>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      <button type="submit" className="btn-ghost">Update email</button>
    </form>
  );
}

function PasswordForm() {
  const { notify } = useAccount();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [error, setError] = useState<string | null>(null);
  const strength = passwordStrength(next);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const problem = passwordProblem(next);
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    try {
      await me.changePassword(current, next);
      setCurrent("");
      setNext("");
      notify("Password changed");
    } catch (err) {
      setError(toApiError(err).message);
    }
  };
  return (
    <form onSubmit={submit} className="card space-y-4 p-6">
      <h2 className="font-display text-xl font-semibold text-ink">Password</h2>
      <Field id="pw-current" label="Current password">
        <input id="pw-current" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required className="input" autoComplete="current-password" />
      </Field>
      <Field id="pw-new" label="New password" hint="At least 8 characters with a letter and a number.">
        <input id="pw-new" type="password" value={next} onChange={(e) => setNext(e.target.value)} required className="input" autoComplete="new-password" />
      </Field>
      <div className="flex gap-1" aria-hidden="true">
        {[1, 2, 3, 4].map((i) => (
          <span key={i} className={`h-1.5 flex-1 rounded-full ${i <= strength ? (strength <= 1 ? "bg-danger" : strength === 2 ? "bg-accent-2" : "bg-success") : "bg-surface-2"}`} />
        ))}
      </div>
      {error && <p role="alert" className="text-sm text-danger">{error}</p>}
      <button type="submit" className="btn-ghost">Change password</button>
    </form>
  );
}

function DangerZone({ email }: { email: string }) {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [pw, setPw] = useState("");
  const [error, setError] = useState<string | null>(null);
  const matches = typed.trim().toLowerCase() === email.toLowerCase();

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!matches) return;
    setError(null);
    try {
      await me.deleteAccount(pw);
      await logout().catch(() => undefined);
      navigate("/", { replace: true });
    } catch (err) {
      setError(toApiError(err).message);
    }
  };

  return (
    <section className="rounded-theme border border-danger/40 bg-danger-soft p-6 lg:col-span-2" aria-labelledby="danger-title">
      <h2 id="danger-title" className="font-display text-xl font-semibold text-ink">Delete account</h2>
      <p className="mt-1 text-sm text-ink-soft">
        Permanently deletes your account, favorites, collections, interests and search history. This can't be undone.
      </p>
      {!open ? (
        <button type="button" className="btn mt-4 bg-danger px-5 text-canvas hover:opacity-90" onClick={() => setOpen(true)}>
          <TrashIcon width={16} height={16} /> Delete my account
        </button>
      ) : (
        <form onSubmit={submit} className="mt-4 grid max-w-xl gap-4 sm:grid-cols-2">
          <Field id="del-email" label={`Type ${email} to confirm`}>
            <input id="del-email" value={typed} onChange={(e) => setTyped(e.target.value)} className="input" autoComplete="off" />
          </Field>
          <Field id="del-pw" label="Password">
            <input id="del-pw" type="password" value={pw} onChange={(e) => setPw(e.target.value)} required className="input" autoComplete="current-password" />
          </Field>
          {error && <p role="alert" className="text-sm text-danger sm:col-span-2">{error}</p>}
          <div className="flex gap-2 sm:col-span-2">
            <button type="submit" disabled={!matches || !pw} className="btn bg-danger px-5 text-canvas hover:opacity-90">Delete forever</button>
            <button type="button" className="btn-ghost" onClick={() => { setOpen(false); setTyped(""); setPw(""); }}>Cancel</button>
          </div>
        </form>
      )}
    </section>
  );
}
