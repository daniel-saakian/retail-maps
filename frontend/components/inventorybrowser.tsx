"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, InventoryItem, InventoryQuery, InventoryResponse, SitePresentationBrand } from "@/lib/api";
import { splitCommaList } from "@/lib/text";
import { formatRate, formatSf, mapsLink, timeAgo, titleCase } from "@/lib/listings";
import SaveProjectionControl from "@/components/SaveProjectionControl";
import { keptAge, keptGet, keptSet, keptTrim, useKept } from "@/lib/keep";

const page_size = 24;
// A loaded page is trusted this long; after that we quietly check the database for changes.
const FRESH_MS = 60_000;
const CHECK_MS = 5 * 60_000;
const CACHE_PREFIX = "inv:data:";
const new_market_mi = 100;

const us_states = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS",
    "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC",
    "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
];

const space_types = [
    "inline", "endcap", "pad", "freestanding", "anchor", "junior anchor", "kiosk", "second floor", "other"
];

const sorts = [
    { value: "newest", label: "Newest first" },
    { value: "updated", label: "Recently updated" },
    { value: "sf_desc", label: "Largest space first" },
    { value: "sf_asc", label: "Smallest space first" },
    { value: "score", label: "Best match first" },
];

interface Filters {
    q: string;
    state: string;
    city: string;
    kind: "" | "space" | "legacy";
    spaceType: string;
    listingType: string;
    minSf: string;
    maxSf: string;
    hasPhoto: boolean;
    hasFlyer: boolean;
    sort: string;
}

const EMPTY: Filters = {
    q: "", state: "", city: "", kind: "", spaceType: "", listingType: "", minSf: "", maxSf: "",
    hasPhoto: false, hasFlyer: false, sort: "newest",
};

function toNumber(s: string): number | null {
    const n = Number(s.replace(/,/g, "").trim());
    return s.trim() !== "" && Number.isFinite(n) && n >= 0 ? Math.floor(n) : null;
}

const inputClass = 
    "rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink outline-none placeholder:text-charcoal/50 focus:border-sky focus:ring-1 focus:ring-sky";

export default function InventoryBrowser({
    brands, brand, onBrandChange,
}: {
    brands: SitePresentationBrand[];
    brand: string;
    onBrandChange: (code: string) => void;
}) {
    // Filters are kept across tab switches; the page number is not, so coming back always shows page 1.
    const [filters, setFilters] = useKept<Filters>("inv:filters", EMPTY);
    const [applied, setApplied] = useKept<Filters>("inv:applied", EMPTY);
    const [offset, setOffset] = useState(0);
    const [checkTick, setCheckTick] = useState(0);
    const buildQuery = (f: Filters, off: number, b: string): InventoryQuery => ({
        q: f.q.trim(),
        state: f.state,
        city: f.city.trim(),
        kind: f.kind,
        space_type: f.spaceType,
        listing_type: f.listingType,
        min_sf: toNumber(f.minSf),
        max_sf: toNumber(f.maxSf),
        has_photo: f.hasPhoto,
        has_flyer: f.hasFlyer,
        sort: f.sort,
        brand: b || null,
        limit: page_size,
        offset: off,
    });
    const cacheKey = (q: InventoryQuery) => CACHE_PREFIX + JSON.stringify(q);
    // Start from the cached page for the current view, if there is one, so there is no spinner on return.
    const [data, setData] = useState<InventoryResponse | null>(
        () => keptGet<InventoryResponse>(cacheKey(buildQuery(applied, 0, brand))) ?? null
    );
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const topRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (filters === applied) return; // nothing typed since the last apply (e.g. just mounted): don't reset the page
        const t = setTimeout(() => {
            setApplied(filters);
            setOffset(0);
        }, 350);
        return () => clearTimeout(t);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [filters]);

    useEffect(() => {
        const ctrl = new AbortController();
        const query = buildQuery(applied, offset, brand);
        const key = cacheKey(query);
        const cached = keptGet<InventoryResponse>(key);
        if (cached) {
            setData(cached);
            setError(null);
            // Recent enough and nothing asked us to look again: no request at all.
            if (keptAge(key) < FRESH_MS) { setLoading(false); return; }
        }
        // A silent check (cached page already on screen) doesn't dim the list.
        setLoading(!cached);
        api.getInventory(query, ctrl.signal)
            .then((d) => {
                if (ctrl.signal.aborted) return;
                // Only replace what's on screen if the database actually returned something different.
                const next = cached && JSON.stringify(cached) === JSON.stringify(d) ? cached : d;
                keptSet(key, next);
                keptTrim(CACHE_PREFIX, 40);
                setData(next);
                setError(null);
            })
            .catch((e) => {
                if (ctrl.signal.aborted || cached) return;
                setError(e instanceof Error ? e.message : String(e));
            })
            .finally(() => { if (!ctrl.signal.aborted) setLoading(false); });
        return () => ctrl.abort();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [applied, offset, brand, checkTick]);

    // New rows in the database: look again when you come back to the browser tab and every few minutes.
    useEffect(() => {
        const check = () => { if (document.visibilityState === "visible") setCheckTick((n) => n + 1); };
        const t = setInterval(check, CHECK_MS);
        document.addEventListener("visibilitychange", check);
        return () => { clearInterval(t); document.removeEventListener("visibilitychange", check); };
    }, []);

    function update<K extends keyof Filters>(key: K, value: Filters[K]) {
        setFilters((f) => ({ ...f, [key]: value }));
    }

    const filtersActive = useMemo(
        () => JSON.stringify({ ...filters, sort: "" }) !== JSON.stringify({ ...EMPTY, sort: "" }),
        [filters]
    );

    function goTo(newOffset: number) {
        setOffset(newOffset);
        topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    const total = data?.total ?? 0;
    const first = total === 0 ? 0 : offset + 1;
    const last = Math.min(offset + page_size, total);

    return (
        <div ref={topRef}>
            <div className="mb-3">
                <input
                    value={filters.q}
                    onChange={(e) => update("q", e.target.value)}
                    placeholder = "Search center, address, city, anchor, brokerage, broker, suite, etc...."
                    aria-label="Search listings"
                    className={`${inputClass} w-full px-4 py-3 text-base`}
                />
            </div>
 
            <div className="mb-3 flex flex-wrap items-center gap-2">
                <select value={filters.state} onChange={(e) => update("state", e.target.value)} aria-label="State" className={inputClass}>
                    <option value="">All states</option>
                    {us_states.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <input
                    value={filters.city}
                    onChange={(e) => update("city", e.target.value)}
                    placeholder="City"
                    aria-label="City"
                    className={`${inputClass} w-36`}
                />
                <select value={filters.spaceType} onChange={(e) => update("spaceType", e.target.value)} aria-label="Space type" className={inputClass}>
                    <option value="">Any space types</option>
                    {space_types.map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}
                </select>
                <select value={filters.listingType} onChange={(e) => update("listingType", e.target.value)} aria-label="Lease or sale" className={inputClass}>
                    <option value="">Lease / sublease / sale</option>
                    <option value="lease">Lease</option>
                    <option value="sublease">Sublease</option>
                    <option value="sale">Sale</option>
                </select>
                <input
                    value={filters.minSf}
                    onChange={(e) => update("minSf", e.target.value)}
                    placeholder="Min SF"
                    inputMode="numeric"
                    aria-label="Minimum Square Feet"
                    className={`${inputClass} w-24`}
                />
                <input
                    value={filters.maxSf}
                    onChange={(e) => update("maxSf", e.target.value)}
                    placeholder="Max SF"
                    inputMode="numeric"
                    aria-label="Maximum Square Feet"
                    className={`${inputClass} w-24`}
                />
            </div>
 
            <div className="mb-5 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-charcoal">
                <label className="flex items-center gap-2">
                    <input type="checkbox" checked={filters.hasPhoto} onChange={(e) => update("hasPhoto", e.target.checked)} />
                    Has photo
                </label>
                <label className="flex items-center gap-2">
                    <input type="checkbox" checked={filters.hasFlyer} onChange={(e) => update("hasFlyer", e.target.checked)} />
                    Has Brochure
                </label>
                <label className="flex items-center gap-2">
                    <span className="text-xs font-semibold uppercase tracking-[0.08em]">Source</span>
                    <select
                        value={filters.kind}
                        onChange={(e) => update("kind", e.target.value as Filters["kind"])}
                        className={inputClass}
                    >
                        <option value="">All</option>
                        <option value="space">Scraped spaces</option>
                        <option value="flyer">Older listings</option>
                    </select>
                </label>
                <label className="flex items-center gap-2">
                    <span className="text-xs font-semibold uppercase tracking-[0.08em]">Brand lens</span>
                    <select value={brand} onChange={(e) => onBrandChange(e.target.value)} className={inputClass}>
                        <option value="">None</option>
                        {brands.map((b) => <option key={b.code} value={b.code}>{b.label}</option>)}
                    </select>
                </label>
                <label className="flex items-center gap-2">
                    <span className="text-xs font-semibold uppercase tracking-[0.08em]">Sort</span>
                    <select value={filters.sort} onChange={(e) => update("sort", e.target.value)} className={inputClass}>
                        {sorts.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                    </select>
                </label>
                {filtersActive && (
                    <button
                        onClick={() => setFilters(EMPTY)}
                        className="text-sm font-semibold uppercase tracking-[0.08em] text-sky hover:underline"
                    >
                        Clear filters
                    </button>
                )}
            </div>
 
            {error && <p className="mb-4 rounded-lg bg-danger/10 p-3 text-sm text-danger-dark">{error}</p>}
 
            <p className="mb-3 text-sm text-charcoal" aria-live="polite">
                {data
                    ? total === 0
                        ? "No listings found"
                        : <>Showing <span className="font-medium text-ink">{first.toLocaleString()}-{last.toLocaleString()}</span> of <span className="font-medium text-ink">{total.toLocaleString()}</span> active listings</>
                    : "Loading listings..."}
            </p>
 
            <div className={`grid grid-cols-1 gap-4 transition-opacity lg:grid-cols-2 ${loading ? "opacity-60" : ""}`}>
                {(data?.items || []).map((item) => (
                    <ListingCard key={item.id} item={item} data={data!} />
                ))}
            </div>
 
            {data && total > page_size && (
                <div className="mt-6 flex items-center justify-between">
                    <button
                        onClick={() => goTo(Math.max(0, offset - page_size))}
                        disabled={offset === 0 || loading}
                        className="rounded-lg border border-line bg-white px-4 py-2 text-sm font-medium text-ink hover:bg-paper-dim disabled:opacity-40"
                    >
                        ← Previous
                    </button>
                    <span className="text-sm text-charcoal">
                        Page {Math.floor(offset / page_size) + 1} of {Math.ceil(total / page_size).toLocaleString()}
                    </span>
                    <button
                        onClick={() => goTo(offset + page_size)}
                        disabled={offset + page_size >= total || loading}
                        className="rounded-lg border border-line bg-white px-4 py-2 text-sm font-medium text-ink hover:bg-paper-dim disabled:opacity-40"
                    >
                        Next →
                    </button>
                </div>
            )}
        </div>
    );
}

function Thumb({ item }: { item: InventoryItem }) {
    const [failed,setFailed] = useState(false);
    if (!item.photo_url || failed) {
        return (
            <div className="flex h-28 w-28 shrink-0 items-center justify-center rounded-md border border-line bg-paper-dim text-[11px] text-charcoal/60">
                No photo
            </div>
        );
    }
    return (
        <div className="shrink-0">
            {/* Brokerage-hosted images: no-referrer avoids hotlink blocks */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
                src={item.photo_url}
                alt={`${item.name}${item.suite ? ` suite ${item.suite}` : ""}`}
                loading="lazy"
                referrerPolicy="no-referrer"
                onError={() => setFailed(true)}
                className="h-28 w-28 rounded-md border border-line object-cover"
            />
            <div className="mt-1 w-28 truncate text-[10px] text-charcoal/70">
                Photo:{" "}
                {item.listing_url ? (
                    <a href={item.listing_url} target="_blank" rel="noopener noreferrer" className="hover:text-sky hover:underline">
                        {item.source || "source"}
                    </a>
                ) : (
                    item.source || "source"
                )}
            </div>
        </div>
    );
}

function Chip({ children, tone }: { children: React.ReactNode; tone?: "sky" | "ink" }) {
    const cls = 
        tone === "sky" ? "bg-sky/10 text-ink" : tone === "ink" ? "bg-ink/5 text-ink" : "border border-line bg-paper text-charcoal";
    return <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${cls}`}>{children}</span>;
}

function ListingCard({ item, data }: { item: InventoryItem; data: InventoryResponse }) {
    const anchors = splitCommaList(item.anchor_names).slice(0,4);
    const location = [item.address, item.city, item.state].filter((x) => x && x !== "-").join(", ");
    const sf = formatSf(item.sf_min, item.sf_max);
    const rate = formatRate(item.rate_min, item.rate_max, item.rate_unit);
    const mi = item.nearest_brand_store_mi;
    const close = mi != null && mi <= data.brand_overlap_mi;
    const newMarket = mi != null && mi > new_market_mi;

    return (
        <article className="flex gap-4 rounded-lg border border-line bg-white p-4">
            <Thumb item={item} />
            <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                        <h3 className="truncate text-base font-semibold text-ink">
                            {item.name}
                            {item.suite && <span className="font-normal text-charcoal"> · Suite {item.suite}</span>}
                        </h3>
                        <a
                            href={mapsLink(item)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block truncate text-sm text-charcoal hover:text-sky hover:underline"
                        >
                            {location || "Location unavailable"}
                        </a>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        {item.score != null && <Chip tone="ink">Score {item.score}</Chip>}
                        <SaveProjectionControl
                            name={item.name}
                            address={item.address}
                            city={item.city}
                            state={item.state}
                        />
                    </div>
                </div>

                <div className="mt-2 flex flex-wrap gap-1.5">
                    {item.listing_type && <Chip tone="sky">{titleCase(item.listing_type)}</Chip>}
                    {item.space_type && <Chip>{titleCase(item.space_type)}</Chip>}
                    {sf && <Chip>{sf}</Chip>}
                    {rate && <Chip>{rate}</Chip>}
                    {item.available_now && <Chip>Available Now</Chip>}
                    {item.kind === "legacy" && <Chip>Older listing</Chip>}
                    {data.brand && mi != null && (
                        <span
                            title={item.nearest_brand_store ? `Nearest: ${item.nearest_brand_store}` : undefined}
                            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                                close ? "bg-caution/15 text-caution" : newMarket ? "bg-sky/10 text-ink" : "bg-success/10 text-success-dark"
                            }`}
                        >
                            {close
                                ? `Overlap · ${mi} mi to ${data.brand_label}`
                                : newMarket
                                    ? `New market · none within ${new_market_mi} mi`
                                    : `${mi.toLocaleString()} mi to ${data.brand_label}`}
                        </span>
                    )}
                </div>

                {anchors.length > 0 && (
                    <p className="mt-2 truncate text-xs text-charcoal/80">
                        Anchors: {anchors.join(", ")}
                        {item.num_tenants > 0 && <> · +{item.num_tenants} tenants</>}
                    </p>
                )}

                <div className="mt-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-t border-line pt-2 text-sm">
                    <div className="min-w-0">
                        <span className="font-medium text-ink">{item.brokerage || "Unknown brokerage"}</span>
                        {item.agent_name && <span className="text-charcoal"> · {item.agent_name}</span>}
                        <span className="ml-2 text-xs text-charcoal/70">New {timeAgo(item.first_seen_at)}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                        {item.phone && <a href={`tel:${item.phone}`} className="font-mono text-xs text-ink hover:text-sky">{item.phone}</a>}
                        {item.email && <a href={`mailto:${item.email}`} className="text-xs text-ink hover:text-sky hover:underline">{item.email}</a>}
                        {item.listing_url &&  (
                            <a href={item.listing_url} target="_blank" rel="noopener noreferrer" className="text-xs font-semibold text-sky hover:underline">
                                View Listing ↗
                            </a>
                        )}
                        {item.flyer_url && (
                            <a href={item.flyer_url} target="_blank" rel="noopener noreferrer" className="text-xs font-semibold text-sky hover:underline">
                                Brochure ↗
                            </a>
                        )}
                    </div>
                </div>
            </div>
        </article>
    );
}