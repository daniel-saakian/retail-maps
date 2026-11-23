"use client";
<<<<<<< HEAD
import SearchForm from "@/components/SearchForm";
import JobCard from "@/components/JobCard";
import { useJobs } from "@/lib/JobsContext";
 
export default function SearchPage() {
    const { jobs, defaultSearchKm, createSearch, dismissSearch } = useJobs();
 
    return(
=======
 
import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { api, DigestPlaza, DigestResponse, SitePresentationBrand } from "@/lib/api";
import { splitCommaList } from "@/lib/text";
import { formatRate, formatSf, mapsLink, timeAgo, titleCase } from "@/lib/listings";
import InventoryBrowser from "@/components/inventorybrowser";
import SaveProjectionControl from "@/components/SaveProjectionControl";
import { keptAge, keptGet, keptSet, useKept } from "@/lib/keep";
 
const WINDOWS = [
    { days: 1, label: "24 hours" },
    { days: 3, label: "3 days" },
    { days: 7, label: "7 days" },
];
 
type SortMode = "location" | "whitespace" | "score";
type Tab = "new" | "browse";
 
const PREFS_KEY = "digest-prefs";
// How long a loaded digest is trusted before we quietly check the database again.
const FRESH_MS = 60_000;
// While the page is open and visible, look for new listings this often.
const POLL_MS = 5 * 60_000;
// Beyond this, the nearest store isn't a useful comparison -- it's a new market for the brand.
const NEW_MARKET_MI = 100;
 
function loadPrefs(): { days?: number; brand?: string; tab?: Tab } {
    try {
        return JSON.parse(window.localStorage.getItem(PREFS_KEY) || "{}");
    } catch {
        return {};
    }
}
 
function savePrefs(prefs: { days: number; brand: string; tab: Tab }) {
    try {
        window.localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
    } catch {
        // Private window or blocked storage -- preferences just won't persist.
    }
}
 
function formatRunTime(iso?: string | null): string {
    if (!iso) return "never";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "unknown";
    return d.toLocaleString(undefined, {
        weekday: "short",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
    });
}
 
function matchesQuery(p: DigestPlaza, q: string): boolean {
    if (!q) return true;
    const hay = [
        p.name, p.city, p.state, p.county, p.address, p.anchor_names,
        ...p.listings.flatMap((l) => [l.brokerage, l.agent_name]),
    ].filter(Boolean).join(" ").toLowerCase();
    return hay.includes(q.toLowerCase());
}
 
function sortPlazas(plazas: DigestPlaza[], mode: SortMode): DigestPlaza[] {
    const copy = [...plazas];
    if (mode === "whitespace") {
        return copy.sort((a, b) => (b.nearest_brand_store_mi ?? -1) - (a.nearest_brand_store_mi ?? -1));
    }
    if (mode === "score") {
        return copy.sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
    }
    return copy.sort((a, b) =>
        a.state.localeCompare(b.state) || a.city.localeCompare(b.city) || a.name.localeCompare(b.name)
    );
}
 
export default function DigestPage() {
    // Everything below lives in a store that survives switching tabs, so coming back shows the page
    // as you left it, with no reload. The digest itself is cached per (window, brand).
    const [days, setDays] = useKept("digest:days", 1);
    const [brand, setBrand] = useKept("digest:brand", "");
    const [prefsLoaded, setPrefsLoaded] = useKept("digest:prefsLoaded", false);
    const [brands, setBrands] = useKept<SitePresentationBrand[]>("digest:brands", []);
    const dataKey = `digest:data:${days}:${brand}`;
    const [data, setData] = useKept<DigestResponse | null>(dataKey, null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [stateFilter, setStateFilter] = useKept("digest:state", "");
    const [query, setQuery] = useKept("digest:query", "");
    const [sort, setSort] = useKept<SortMode>("digest:sort", "location");
    const [showRemoved, setShowRemoved] = useKept("digest:showRemoved", false);
    const [reloadKey, setReloadKey] = useState(0);
    const seenReload = useRef(0);
    const [pollKey, setPollKey] = useState(0); // bumped by the background check; refreshes without dimming the page
    const seenPoll = useRef(0);
    const [tab, setTab] = useKept<Tab>("digest:tab", "new");
    const [browseVisited, setBrowseVisited] = useKept("digest:browseVisited", false);

    useEffect(() => {
        if (!prefsLoaded) {
            const prefs = loadPrefs();
            if (prefs.days && WINDOWS.some((w) => w.days === prefs.days)) setDays(prefs.days);
            if (prefs.brand) setBrand(prefs.brand);
            if (prefs.tab === "browse") { setTab("browse"); setBrowseVisited(true); }
            setPrefsLoaded(true);
        }
        if (brands.length === 0 || keptAge("digest:brands") > POLL_MS) {
            api.listSitePresentationBrands().then(setBrands).catch(() => { if (brands.length === 0) setBrands([]); });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        if (!prefsLoaded) return;
        savePrefs({ days, brand, tab });
        const forced = reloadKey !== seenReload.current || pollKey !== seenPoll.current;
        const quiet = reloadKey === seenReload.current && pollKey !== seenPoll.current;
        seenReload.current = reloadKey;
        seenPoll.current = pollKey;
        // Already have this view and it's recent: show it as is, no request at all.
        if (keptGet<DigestResponse | null>(dataKey) && !forced && keptAge(dataKey) < FRESH_MS) return;
        let cancelled = false;
        if (!quiet) setLoading(true);
        setError(null);
        api.getDigest(days, brand || null)
            .then((d) => {
                if (cancelled) return;
                // Only swap the page's data when the database actually has something different.
                const prev = keptGet<DigestResponse | null>(dataKey);
                keptSet(dataKey, prev && JSON.stringify(prev) === JSON.stringify(d) ? prev : d);
            })
            .catch((e) => { if (!cancelled && !quiet) setError(e instanceof Error ? e.message : String(e)); })
            .finally(() => { if (!cancelled) setLoading(false); });
        return () => { cancelled = true; };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [days, brand, tab, prefsLoaded, reloadKey, pollKey]);

    // New rows in the database show up on their own: check when you come back to the browser tab,
    // and every few minutes while the page is open.
    useEffect(() => {
        if (!prefsLoaded) return;
        const check = () => {
            if (document.visibilityState === "visible" && keptAge(dataKey) >= FRESH_MS) setPollKey((k) => k + 1);
        };
        const t = setInterval(check, POLL_MS);
        document.addEventListener("visibilitychange", check);
        return () => { clearInterval(t); document.removeEventListener("visibilitychange", check); };
    }, [prefsLoaded, dataKey]);

    useEffect(() => {
        if (!brand && sort === "whitespace") setSort("location");
    }, [brand, sort]);
 
    const states = useMemo(() => {
        const all = new Set<string>();
        (data?.new || []).forEach((p) => all.add(p.state));
        (data?.removed || []).forEach((p) => all.add(p.state));
        return Array.from(all).filter((s) => s && s !== "-").sort();
    }, [data]);
 
    const visibleNew = useMemo(() => {
        const rows = (data?.new || []).filter(
            (p) => (!stateFilter || p.state === stateFilter) && matchesQuery(p, query)
        );
        return sortPlazas(rows, sort);
    }, [data, stateFilter, query, sort]);
 
    const visibleRemoved = useMemo(
        () => sortPlazas(
            (data?.removed || []).filter(
                (p) => (!stateFilter || p.state === stateFilter) && matchesQuery(p, query)
            ),
            "location"
        ),
        [data, stateFilter, query]
    );
 
    const newListingCount = visibleNew.reduce((n, p) => n + p.listings.length, 0);
    const removedListingCount = visibleRemoved.reduce((n, p) => n + p.listings.length, 0);
    const overlapCount = data?.brand
        ? visibleNew.filter((p) => p.nearest_brand_store_mi != null && p.nearest_brand_store_mi <= data.brand_overlap_mi).length
        : 0;
    const windowLabel = WINDOWS.find((w) => w.days === days)?.label || `${days} days`;
    const filtersActive = Boolean(stateFilter || query);
 
    return (
>>>>>>> f8bc158 (major changes)
        <main className="mx-auto max-w-6xl px-6 py-10">
            <header className="mb-6">
                <h1 className="font-display text-3xl font-bold text-ink">Daily Digest</h1>
                <div className="wedge-divider mt-3 mb-2 max-w-xs">
                    <span className="whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.18em] text-charcoal">
                        Daily Listings
                    </span>
                </div>
<<<<<<< HEAD
                <p className="text-sm text-charcoal">
                    Search a city, watch it run, and get the exportable map
                </p>
            </header>
 
            <SearchForm defaultSearchKm={defaultSearchKm} onSubmit={createSearch} />
 
            <div className="mt-8 flex flex-col gap-5">
                {jobs.length === 0 && (
                    <p className="rounded-lg border border-dashed border-line bg-paper-dim/50 p-6 text-center text-sm text-charcoal/70">
                        No Searches Yet
=======
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm text-charcoal">
                        New retail space from the brokerage feeds, grouped by center, plus every active listing on file.
                        {data && <> Last refreshed <span className="font-medium text-ink">{formatRunTime(data.last_run_at)}</span>.</>}
>>>>>>> f8bc158 (major changes)
                    </p>
                    <button
                        onClick={() => setReloadKey((k) => k + 1)}
                        disabled={loading}
                        className="shrink-0 text-xs font-semibold uppercase tracking-[0.08em] text-charcoal hover:text-ink disabled:opacity-50"
                    >
                        {loading ? "Refreshing..." : "Refresh"}
                    </button>
                </div>
            </header>
 
            {data?.run_is_stale && (
                <div className="mb-5 rounded-lg border border-caution/30 bg-caution/10 p-3 text-sm text-caution">
                    No listing has been added or re-confirmed since {formatRunTime(data.last_run_at)}, so this page
                    may be missing new space. If you&apos;ve run the scraper since then, check it&apos;s writing to the
                    database this site reads from.
                </div>
            )}
 
            <div className="mb-6 flex gap-1 border-b border-line" role="tablist" aria-label="Digest sections">
                {([
                    { id: "new", label: "What\u2019s new" },
                    { id: "browse", label: "Browse all listings" },
                ] as { id: Tab; label: string }[]).map((t) => (
                    <button
                        key={t.id}
                        role="tab"
                        aria-selected={tab === t.id}
                        onClick={() => { setTab(t.id); if (t.id === "browse") setBrowseVisited(true); }}
                        className={`-mb-px border-b-2 px-4 py-2 text-sm font-semibold transition ${
                            tab === t.id ? "border-sky text-ink" : "border-transparent text-charcoal hover:text-ink"
                        }`}
                    >
                        {t.label}
                        {t.id === "browse" && data?.active_listing_count != null && (
                            <span className="ml-2 text-xs font-normal text-charcoal/70">
                                {data.active_listing_count.toLocaleString()}
                            </span>
                        )}
                    </button>
                ))}
            </div>
 
            {browseVisited && (
                <div hidden={tab !== "browse"}>
                    <InventoryBrowser brands={brands} brand={brand} onBrandChange={setBrand} />
                </div>
            )}
 
            {tab === "new" && (<>
            <div className="mb-6 flex flex-wrap items-center gap-3">
                <div className="flex rounded-lg border border-line bg-white p-0.5" role="group" aria-label="Time window">
                    {WINDOWS.map((w) => (
                        <button
                            key={w.days}
                            onClick={() => setDays(w.days)}
                            aria-pressed={days === w.days}
                            className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                                days === w.days ? "bg-ink text-white" : "text-charcoal hover:bg-paper-dim"
                            }`}
                        >
                            {w.label}
                        </button>
                    ))}
                </div>
 
                <label className="flex items-center gap-2 text-sm text-charcoal">
                    <span className="text-xs font-semibold uppercase tracking-[0.08em]">Brand lens</span>
                    <select
                        value={brand}
                        onChange={(e) => setBrand(e.target.value)}
                        className="rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                    >
                        <option value="">None</option>
                        {brands.map((b) => (
                            <option key={b.code} value={b.code}>{b.label}</option>
                        ))}
                    </select>
                </label>
 
                <select
                    value={stateFilter}
                    onChange={(e) => setStateFilter(e.target.value)}
                    aria-label="State"
                    className="rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                >
                    <option value="">All states</option>
                    {states.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
 
                <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Filter by center, city, brokerage..."
                    className="min-w-[220px] flex-1 rounded-lg border border-line bg-white px-4 py-2 text-sm text-ink outline-none placeholder:text-charcoal/50 focus:border-sky focus:ring-1 focus:ring-sky"
                />
            </div>
 
            {error && (
                <p className="mb-4 rounded-lg bg-danger/10 p-3 text-sm text-danger-dark">{error}</p>
            )}
 
            {data && (
                <section className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-4" aria-label="Summary">
                    <Stat label={`New listings · ${windowLabel}`} value={newListingCount} accent />
                    <Stat label="Centers with new space" value={visibleNew.length} />
                    <Stat
                        label="Leased / removed"
                        value={data.removed_tracking_enabled ? removedListingCount : "—"}
                        hint={data.removed_tracking_enabled ? undefined : "Needs one-time database update"}
                    />
                    <Stat
                        label={filtersActive ? "Active listings (all)" : "Active listings tracked"}
                        value={data.active_listing_count ?? "—"}
                        hint={
                            data.active_space_count != null && data.active_legacy_count != null
                                ? `${data.active_space_count.toLocaleString()} scraped · ${data.active_legacy_count.toLocaleString()} older`
                                : undefined
                        }
                    />
                </section>
            )}
 
            {data?.new_truncated && (
                <p className="mb-5 rounded-lg border border-line bg-paper-dim/60 px-4 py-3 text-sm text-charcoal">
                    Showing the newest {data.new_listing_count.toLocaleString()} of {data.new_total.toLocaleString()} new
                    listings in this window. Use <button onClick={() => { setTab("browse"); setBrowseVisited(true); }} className="font-semibold text-sky hover:underline">Browse all listings</button> to
                    search the rest, or pick a shorter window.
                </p>
            )}
 
            {data?.brand && (
                <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-paper-dim/60 px-4 py-3 text-sm text-charcoal">
                    <p>
                        Showing distance to the nearest existing <span className="font-semibold text-ink">{data.brand_label}</span>
                        {" "}({data.brand_store_count} stores on file).
                        {overlapCount > 0 && (
                            <> <span className="font-semibold text-caution">{overlapCount}</span> center{overlapCount === 1 ? " is" : "s are"} within {data.brand_overlap_mi} mi of one.</>
                        )}
                        {data.brand_store_count === 0 && " No store list found for this brand, so distances are blank."}
                    </p>
                    <SortToggle sort={sort} setSort={setSort} showWhitespace />
                </div>
            )}
            {data && !data.brand && visibleNew.length > 1 && (
                <div className="mb-4 flex justify-end">
                    <SortToggle sort={sort} setSort={setSort} showWhitespace={false} />
                </div>
            )}
 
            {loading && !data && <p className="text-sm text-charcoal">Loading today&apos;s listings...</p>}
 
            {data && visibleNew.length === 0 && (
                <div className="rounded-lg border border-dashed border-line bg-paper-dim/50 p-8 text-center text-sm text-charcoal/80">
                    {filtersActive
                        ? "No new listings match those filters."
                        : `No new listings in the last ${windowLabel}.`}
                    {!filtersActive && days === 1 && (
                        <>
                            {" "}
                            <button onClick={() => setDays(7)} className="font-semibold text-sky hover:underline">
                                See the last 7 days
                            </button>
                            {" "}or{" "}
                            <Link href="/search" className="font-semibold text-sky hover:underline">run a new search</Link>.
                        </>
                    )}
                </div>
            )}
 
            <div className={`flex flex-col gap-4 transition-opacity ${loading ? "opacity-60" : ""}`}>
                {visibleNew.map((p, i) => {
                    const prev = visibleNew[i - 1];
                    const showStateHeader = sort === "location" && (!prev || prev.state !== p.state);
                    return (
                        <div key={p.id}>
                            {showStateHeader && (
                                <h2 className="mb-2 mt-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-charcoal first:mt-0">
                                    {p.state} · {visibleNew.filter((x) => x.state === p.state).length} center
                                    {visibleNew.filter((x) => x.state === p.state).length === 1 ? "" : "s"}
                                </h2>
                            )}
                            <PlazaCard plaza={p} digest={data!} variant="new" />
                        </div>
                    );
                })}
            </div>
 
            {data?.removed_tracking_enabled && visibleRemoved.length > 0 && (
                <section className="mt-10">
                    <button
                        onClick={() => setShowRemoved((s) => !s)}
                        aria-expanded={showRemoved}
                        className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink hover:text-sky"
                    >
                        <span className={`inline-block transition-transform ${showRemoved ? "rotate-90" : ""}`}>›</span>
                        Leased or removed · {removedListingCount} listing{removedListingCount === 1 ? "" : "s"}
                    </button>
                    {showRemoved && (
                        <div className="flex flex-col gap-3">
                            {visibleRemoved.map((p) => (
                                <PlazaCard key={p.id} plaza={p} digest={data} variant="removed" />
                            ))}
                        </div>
                    )}
                </section>
            )}
            </>)}
        </main>
    );
}
<<<<<<< HEAD
=======
 
function SortToggle({
    sort, setSort, showWhitespace,
}: { sort: SortMode; setSort: (s: SortMode) => void; showWhitespace: boolean }) {
    const options: { value: SortMode; label: string }[] = [
        { value: "location", label: "By location" },
        { value: "score", label: "Highest score" },
        ...(showWhitespace ? [{ value: "whitespace" as SortMode, label: "Farthest from brand" }] : []),
    ];
    return (
        <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.08em] text-charcoal">
            Sort
            <select
                value={sort}
                onChange={(e) => setSort(e.target.value as SortMode)}
                className="rounded-md border border-line bg-white px-2 py-1 text-sm font-normal normal-case tracking-normal text-ink outline-none focus:border-sky"
            >
                {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
        </label>
    );
}
 
function Stat({
    label, value, accent, hint,
}: { label: string; value: number | string; accent?: boolean; hint?: string }) {
    return (
        <div className="rounded-lg border border-line bg-white px-4 py-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-charcoal">{label}</div>
            <div className={`mt-1 font-display text-2xl font-bold ${accent ? "text-sky" : "text-ink"}`}>
                {typeof value === "number" ? value.toLocaleString() : value}
            </div>
            {hint && <div className="mt-0.5 text-xs text-charcoal/70">{hint}</div>}
        </div>
    );
}
 
function BrandBadge({ plaza, digest }: { plaza: DigestPlaza; digest: DigestResponse }) {
    if (!digest.brand || plaza.nearest_brand_store_mi == null) return null;
    const mi = plaza.nearest_brand_store_mi;
    const close = mi <= digest.brand_overlap_mi;
    const newMarket = mi > NEW_MARKET_MI;
    const label = close
        ? `Overlap · ${mi} mi to nearest ${digest.brand_label}`
        : newMarket
            ? `New market · none within ${NEW_MARKET_MI} mi`
            : `${mi.toLocaleString()} mi to nearest ${digest.brand_label}`;
    return (
        <span
            title={plaza.nearest_brand_store ? `Nearest: ${plaza.nearest_brand_store}, ${mi.toLocaleString()} mi` : undefined}
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                close ? "bg-caution/15 text-caution" : newMarket ? "bg-sky/10 text-ink" : "bg-success/10 text-success-dark"
            }`}
        >
            {label}
        </span>
    );
}
 
function PlazaCard({
    plaza, digest, variant,
}: { plaza: DigestPlaza; digest: DigestResponse; variant: "new" | "removed" }) {
    const anchors = splitCommaList(plaza.anchor_names).slice(0, 6);
    const location = [plaza.address, plaza.city, plaza.state].filter((x) => x && x !== "-").join(", ");
    const removed = variant === "removed";
 
    return (
        <article className={`rounded-lg border border-line bg-white p-5 ${removed ? "opacity-80" : ""}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                    <h3 className="text-base font-semibold text-ink">{plaza.name}</h3>
                    <a
                        href={mapsLink(plaza)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-charcoal hover:text-sky hover:underline"
                    >
                        {location || "Location unavailable"}
                    </a>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    <BrandBadge plaza={plaza} digest={digest} />
                    {plaza.score != null && (
                        <span className="inline-flex items-center rounded-full bg-ink/5 px-2.5 py-0.5 text-xs font-semibold text-ink">
                            Score {plaza.score}
                        </span>
                    )}
                    {!removed && (
                        <SaveProjectionControl
                            name={plaza.name}
                            address={plaza.address}
                            city={plaza.city}
                            state={plaza.state}
                        />
                    )}
                </div>
            </div>
 
            {anchors.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                    {anchors.map((a) => (
                        <span key={a} className="rounded border border-line bg-paper px-2 py-0.5 text-xs text-charcoal">
                            {a}
                        </span>
                    ))}
                    {plaza.num_tenants > 0 && (
                        <span className="px-1 py-0.5 text-xs text-charcoal/70">+ {plaza.num_tenants} other tenants</span>
                    )}
                </div>
            )}
 
            <ul className="mt-4 divide-y divide-line border-t border-line">
                {plaza.listings.map((l) => {
                    const sf = formatSf(l.sf_min, l.sf_max);
                    const rate = formatRate(l.rate_min, l.rate_max, l.rate_unit);
                    const details = [
                        l.suite ? `Suite ${l.suite}` : "",
                        l.space_type ? titleCase(l.space_type) : "",
                        l.listing_type ? titleCase(l.listing_type) : "",
                        sf,
                        rate,
                    ].filter(Boolean);
                    return (
                        <li key={l.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2.5 text-sm">
                            <div className="flex min-w-0 items-center gap-3">
                                {l.photo_url && (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img
                                        src={l.photo_url}
                                        alt=""
                                        loading="lazy"
                                        referrerPolicy="no-referrer"
                                        onError={(e) => { e.currentTarget.style.display = "none"; }}
                                        className="h-12 w-12 shrink-0 rounded border border-line object-cover"
                                    />
                                )}
                                <div className="min-w-0">
                                    {details.length > 0 && (
                                        <div className="text-xs font-medium text-ink">{details.join(" · ")}</div>
                                    )}
                                    <span className="font-medium text-ink">{l.brokerage || "Unknown brokerage"}</span>
                                    {l.agent_name && <span className="text-charcoal"> · {l.agent_name}</span>}
                                    <span className="ml-2 text-xs text-charcoal/70">
                                        {removed ? `Removed ${timeAgo(l.deactivated_at)}` : `New ${timeAgo(l.first_seen_at)}`}
                                    </span>
                                </div>
                            </div>
                            <div className="flex flex-wrap items-center gap-3 text-sm">
                                {l.phone && (
                                    <a href={`tel:${l.phone}`} className="font-mono text-xs text-ink hover:text-sky">{l.phone}</a>
                                )}
                                {l.email && (
                                    <a href={`mailto:${l.email}`} className="text-ink hover:text-sky hover:underline">{l.email}</a>
                                )}
                                {l.listing_url && (
                                    <a
                                        href={l.listing_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="font-semibold text-sky hover:underline"
                                    >
                                        View listing ↗
                                    </a>
                                )}
                                {l.flyer_url && (
                                    <a
                                        href={l.flyer_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="font-semibold text-sky hover:underline"
                                    >
                                        Brochure ↗
                                    </a>
                                )}
                            </div>
                        </li>
                    );
                })}
            </ul>
        </article>
    );
}
>>>>>>> f8bc158 (major changes)
