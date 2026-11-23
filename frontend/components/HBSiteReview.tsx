"use client";







import { forwardRef, useCallback, useEffect, useImperativeHandle, useMemo, useRef, useState } from "react";
import {
    FieldSource,
    FormState,
    ListingCandidate,
    PrefillResponse,
    ReviewSchema,
    ReviewTableSpec,
    Swot,
    SwotKey,
    TableRow,
    emptySwot,
    hbReview,
    saveBlob,
} from "@/lib/hbReview";
import { useKept } from "@/lib/keep";

export interface HBSiteReviewHandle {
    prefill: (address: string, coords?: {lat: number, lon: number}) => Promise<void>;
    cancel: () => void;
}

interface Props {
    onBusyChange?: (busy: boolean) => void;
    /** Called when a saved draft is opened or restored, so the page's address box can match it. */
    onAddress?: (address: string) => void;
}

interface DraftInfo {
    key: string;
    address: string;
    savedAt: number;
    filled: number;
}

const DRAFT_PREFIX = "hb-review:";
const LAST_DRAFT = "hb-review-last";

// The one request that may be running. Module-level (not a ref) so it can still be cancelled, and still
// finishes into the store, after you've clicked to another tab and come back.
let inflight: AbortController | null = null;

function readDrafts(): DraftInfo[] {
    const out: DraftInfo[] = [];
    try {
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (!key || !key.startsWith(DRAFT_PREFIX)) continue;
            try {
                const d = JSON.parse(localStorage.getItem(key) || "{}");
                if (!d.context) continue;
                out.push({
                    key,
                    address: d.address || key.slice(DRAFT_PREFIX.length).replace(/-/g, " "),
                    savedAt: d.savedAt || 0,
                    filled: Object.values((d.fields || {}) as Record<string, string>).filter((v) => (v || "").trim()).length,
                });
            } catch {
                /* skip a damaged entry */
            }
        }
    } catch {
        /* storage blocked */
    }
    return out.sort((a, b) => b.savedAt - a.savedAt);
}

type Meta = { source: FieldSource; note?: string | null; edited?: boolean };

const SOURCE_STYLE: Record<FieldSource, {label: string; cls: string}> = {
    auto: { label: "Auto", cls: "bg-sky/10 text-sky border-sky/30" },
    listing: { label: "Listing", cls: "bg-brass/10 text-brass border-brass/40"},
    ai: {label: "Write-up", cls: "bg-caution/10 text-caution border-caution/30"},
    manual: {label: "Manual", cls: "bg-paper-dim text-charcoal/70 border-line" },
};

const SWOT_LABELS: Record<SwotKey, string> = {
    strengths: "Strengths",
    weaknesses: "Weaknesses",
    opportunities: "Opportunities",
    threats: "Threats",
};

const PREFILL_STAGES =[
    "Geocoding address...",
    "Pulling Demographics (1/3/5) mi...",
    "Checking traffic counts...",
    "Mapping the center and co-tenants...",
    "Finding demand drivers and competitors...",
    "Looking for listed spaces...",
];

function storageKey(address: string) {
    return DRAFT_PREFIX + address.trim().toLowerCase().replace(/\s+/g, "-");
}

const HBSiteReview = forwardRef<HBSiteReviewHandle, Props>(function HBSiteReview({ onBusyChange, onAddress }, ref) {
    // Everything here is kept (not plain useState) so the form is exactly as you left it when you click to
    // another tab and come back, and a prefill that is still running finishes into the same form.
    const [schema, setSchema] = useKept<ReviewSchema | null>("hb:schema", null);
    const [address, setAddress] = useKept("hb:address", "");
    const [fields, setFields] = useKept<Record<string, string>>("hb:fields", {});
    const [meta, setMeta] = useKept<Record<string, Meta>>("hb:meta", {});
    const [tables, setTables] = useKept<Record<string, TableRow[]>>("hb:tables", {});
    const [swot, setSwot] = useKept<Swot>("hb:swot", emptySwot);
    const [context, setContext] = useKept<Record<string, unknown> | null>("hb:context", null);
    const [listings, setListings] = useKept<ListingCandidate[]>("hb:listings", []);
    const [listingId, setListingId] = useKept<string>("hb:listingId", "");
    const [warnings, setWarnings] = useKept<string[]>("hb:warnings", []);

    const [busy, setBusy] = useKept<null | "prefill" | "render" | "download">("hb:busy", null);
    const [stage, setStage] = useState(0);
    const [error, setError] = useKept<string | null>("hb:error", null);
    const [notice, setNotice] = useKept<string | null>("hb:notice", null);
    const [openSections, setOpenSections] = useKept<Set<string>>("hb:open", () => new Set(["s1", "s2", "s3", "s4"]));
    const [onlyEmpty, setOnlyEmpty] = useKept("hb:onlyEmpty", false);
    const [previewOpen, setPreviewOpen] = useState(false);
    const [drafts, setDrafts] = useState<DraftInfo[]>([]);
    const [draftsOpen, setDraftsOpen] = useState(false);

    const previewRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!schema) hbReview.schema().then(setSchema).catch((e) => setError((e as Error).message));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // On a fresh load (no form in memory) bring back the last draft you were working on, no prompts.
    useEffect(() => {
        setDrafts(readDrafts());
        if (context || busy) return;
        try {
            const key = localStorage.getItem(LAST_DRAFT);
            const raw = key ? localStorage.getItem(key) : null;
            if (!raw) return;
            const d = JSON.parse(raw);
            if (!d.context) return;
            applyDraft(d);
            setNotice(`Restored your last draft${d.address ? ` for ${d.address}` : ""}.`);
        } catch {
            /* nothing to restore */
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useEffect(() => {
        onBusyChange?.(busy !== null);
    }, [busy, onBusyChange]);

    useEffect(() => {
        if (busy !== "prefill") return setStage(0);
        const t = setInterval(() => setStage((i) => Math.min(i + 1, PREFILL_STAGES.length - 1)), 4500);
        return () => clearInterval(t);
    }, [busy]);

    
    useEffect(() => {
        if (!address || !context) return;
        try {
            localStorage.setItem(
                storageKey(address),
                JSON.stringify({ address, fields, meta, tables, swot, context, listings, listingId, savedAt: Date.now() })
            );
            localStorage.setItem(LAST_DRAFT, storageKey(address));
            setDrafts(readDrafts());
        } catch {
            /* Storage full or blocked -- non-essential */
        }
    }, [address, fields, meta, tables, swot, context, listings, listingId]);

    function applyDraft(s: {
        address?: string; fields?: Record<string, string>; meta?: Record<string, Meta>;
        tables?: Record<string, TableRow[]>; swot?: Swot; context?: Record<string, unknown> | null;
        listings?: ListingCandidate[]; listingId?: string;
    }) {
        if (s.address) {
            setAddress(s.address);
            onAddress?.(s.address);
        }
        setFields(s.fields || {});
        setMeta(s.meta || {});
        setTables(s.tables || {});
        setSwot(s.swot || emptySwot());
        setContext(s.context || null);
        setListings(s.listings || []);
        setListingId(s.listingId || "");
        setWarnings([]);
        setError(null);
    }

    function openDraft(d: DraftInfo) {
        try {
            const raw = localStorage.getItem(d.key);
            if (!raw) return;
            applyDraft({ address: d.address, ...JSON.parse(raw) });
            setNotice(`Opened the draft for ${d.address}.`);
            setDraftsOpen(false);
        } catch {
            setError("That draft couldn't be opened.");
        }
    }

    function deleteDraft(d: DraftInfo) {
        if (!window.confirm(`Delete the saved draft for ${d.address}?`)) return;
        try {
            localStorage.removeItem(d.key);
            if (localStorage.getItem(LAST_DRAFT) === d.key) localStorage.removeItem(LAST_DRAFT);
        } catch {
            /* ignore */
        }
        setDrafts(readDrafts());
    }

    const state = useCallback((): FormState => ({ fields, tables, swot }), [fields, tables, swot]);



    useImperativeHandle(ref, () => ({
        cancel: () => inflight?.abort(),
        prefill: async (addr: string, coords?: { lat: number; lon: number }) => {
            setError(null);
            setNotice(null);
            setAddress(addr);

            try {
                const saved = localStorage.getItem(storageKey(addr));
                if (saved && !coords) {
                    const s = JSON.parse(saved);
                    const when = new Date(s.savedAt).toLocaleString();
                    if (window.confirm(`You have a saved draft for this address from ${when}. Load it instead of re-pulling data?`)) {
                        applyDraft({ ...s, address: addr });
                        return;
                    }
                }
            } catch {
                /* ignore */
            }

            const controller = new AbortController();
            inflight = controller;
            setBusy("prefill");
            try {
                const res: PrefillResponse = await hbReview.prefill(addr, coords, controller.signal);
                const f: Record<string, string> = {};
                const m: Record<string, Meta> = {};
                for (const [id, v] of Object.entries(res.fields)) {
                    f[id] = v.value;
                    m[id] = { source: v.source, note: v.note };
                }
                setFields(f);
                setMeta(m);
                setTables(res.tables || {});
                setSwot(emptySwot());
                setContext(res.context);
                setListings(res.listings || []);
                setWarnings(res.warnings || []);
                setListingId("");
                if (res.listings?.length === 1) applyListing(res.listings[0], f, m);
                setNotice(
                    `Prefilled ${Object.keys(f).length} fields` +
                        (res.listings?.length ? ` - ${res.listings.length} listed space(s) found at this center.` : ".")
                );
            } catch (e) {
                if ((e as Error).name === "AbortError") setNotice("Prefill cancelled.");
                else setError((e as Error).message);
            } finally {
                setBusy(null);
                inflight = null;
            }
        },
    }));



    function applyListing(
        l: ListingCandidate | null,
        baseFields: Record<string, string> = fields,
        baseMeta: Record<string, Meta> = meta
    ) {
        const f = { ...baseFields };
        const m = { ...baseMeta };

        for (const [id, info] of Object.entries(m)) {
            if (info.source === "listing" && !info.edited) {
                delete f[id];
                delete m[id];
            }
        }
        if (l) {
            for (const [id, v] of Object.entries(l.fields)) {
                const cur = (f[id] || "").trim();
                const curMeta = m[id];

                if (!cur || (curMeta && curMeta.source === "auto" && !curMeta.edited)) {
                    f[id] = v.value;
                    m[id] = { source: "listing", note:v.note };
                }
            }
        }
        setFields(f);
        setMeta(m);
        setListingId(l?.id || "");
    }



    async function renderPreview() {
        setBusy("render");
        setError(null);
        try {
            const { blob } = await hbReview.render(state());
            setPreviewOpen(true);
            await new Promise((r) => setTimeout(r, 0));
            const { renderAsync } = await import("docx-preview");
            if (previewRef.current) {
                previewRef.current.innerHTML = "";
                await renderAsync(blob, previewRef.current, undefined, {
                    inWrapper: true,
                    ignoreWidth: false,
                    breakPages: true,
                    experimental: true,
                });
            }
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setBusy(null);
        }
    }

    async function download() {
        setBusy("download");
        setError(null);
        try {
            const {blob, filename} = await hbReview.render(state());
            saveBlob(blob, filename);
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setBusy(null);
        }
    }



    function setField(id: string, value: string) {
        setFields((f) => ({ ...f, [id]: value }));
        setMeta((m) => ({ ...m, [id]: { ...(m[id] || {source: "manual"}), edited: true } }));
    }

    function setCell(spec: ReviewTableSpec, i: number, key: string, value: string) {
        setTables((t) => {
            const rows = [...(t[spec.id] || [])];
            while (rows.length <= i) rows.push({});
            rows[i] = { ...rows[i], [key]: value };
            return { ...t, [spec.id]: rows };
        });
    }

    function addRow(spec: ReviewTableSpec) {
        setTables((t) => ({ ...t, [spec.id]: [...(t[spec.id] || []), {}].slice(0, spec.max_rows) }));
    }

    function removeRow(spec: ReviewTableSpec, i: number) {
        setTables((t) => ({ ...t, [spec.id]: (t[spec.id] || []).filter((_, j) => j !== i) }));
    }

    function setSwotItem(k: SwotKey, i:number, value: string) {
        setSwot((s) => {
            const items = [...s[k]];
            while (items.length <= i) items.push("");
            items[i] = value;
            return { ...s, [k]: items };
        });
    }



    const progress = useMemo(() => {
        if (!schema) return { filled: 0, total: 0, bySection: {} as Record<string, [number, number]> };
        const bySection: Record<string, [number, number]> = {};
        let filled = 0;
        for (const f of schema.fields) {
            const has = !!(fields[f.id] || "").trim();
            bySection[f.section] = bySection[f.section] || [0, 0];
            bySection[f.section][1] += 1;
            if (has) {
                bySection[f.section][0] += 1;
                filled += 1;
            }
        }
        return { filled, total: schema.fields.length, bySection };
    }, [schema, fields]);

    if (!schema) {
        return error ? (
            <p className="mt-6 rounded-lg bg-danger/10 p-3 text-sm text-danger-dark">Couldn&apos;t load the form: {error}</p>
        ) : (
            <p className="mt-6 text-sm text-charcoal/70">Loading form...</p>
        );
    }

    const hasData = context !== null;
    const listing = listings.find((l) => l.id === listingId) || null;



    return (
        <section className="mt-6">
            {busy === "prefill" && (
                <div className="mb-4 rounded-xl border border-line bg-white p-4 shadow-sm">
                    <p className="text-xs font-medium text-charcoal">{PREFILL_STAGES[stage]}</p>
                    <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-paper">
                        <div
                            className="h-full rounded-full bg-gradient-to-r from-sky to-ink transition-[width] duration-700"
                            style={{ width: `${((stage + 1) / PREFILL_STAGES.length) * 92}%` }}
                        />
                    </div>
                    <p className="mt-2 text-xs text-charcoal/70">Usually 30-90 seconds. Pulling live Census, DOT and OSM data.</p>
                </div>
            )}

            {drafts.length > 0 && (
                <div className="mb-4 rounded-xl border border-line bg-white shadow-sm">
                    <button
                        type="button"
                        onClick={() => setDraftsOpen((v) => !v)}
                        aria-expanded={draftsOpen}
                        className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-ink"
                    >
                        <span>Saved drafts <span className="font-normal text-charcoal/70">({drafts.length})</span></span>
                        <span className="text-xs text-charcoal/70">{draftsOpen ? "Hide" : "Show"}</span>
                    </button>
                    {draftsOpen && (
                        <ul className="divide-y divide-line border-t border-line">
                            {drafts.map((d) => (
                                <li key={d.key} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5 text-sm">
                                    <div className="min-w-0">
                                        <p className="truncate font-medium text-ink">{d.address}</p>
                                        <p className="text-xs text-charcoal/70">
                                            {d.filled} fields filled
                                            {d.savedAt ? ` · saved ${new Date(d.savedAt).toLocaleString()}` : ""}
                                            {d.key === storageKey(address) && " · open now"}
                                        </p>
                                    </div>
                                    <div className="flex shrink-0 gap-3">
                                        <button
                                            type="button"
                                            onClick={() => openDraft(d)}
                                            disabled={busy !== null}
                                            className="text-xs font-semibold text-sky hover:underline disabled:opacity-40"
                                        >
                                            Open
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => deleteDraft(d)}
                                            className="text-xs font-semibold text-danger-dark hover:underline"
                                        >
                                            Delete
                                        </button>
                                    </div>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}

            {error && <p className="mb-3 rounded-lg bg-danger/10 p-3 text-sm text-danger-dark">{error}</p>}
            {notice && !error && <p className="mb-3 rounded-lg bg-success/10 p-3 text-sm text-success-dark">{notice}</p>}
            {warnings.length > 0 && (
                <details className="mb-3 rounded-lg border border-caution/30 bg-caution/5 p-3 text-sm text-caution">
                    <summary className="cursor-pointer font-semibold">
                        {warnings.length} data source{warnings.length > 1 ? "s" : ""} unavailable - those fields are left blank
                    </summary>
                    <ul className="mt-2 list-disc pl-5 text-xs">
                        {warnings.map((w) => (
                            <li key={w}>{w}</li>
                        ))}
                    </ul>
                </details>
            )}

            {!hasData && busy !== "prefill" && (
                <div className="rounded-xl border border-dashed border-line bg-paper p-6 text-sm text-charcoal">
                    Enter the site address above and press <b><i>Prefill Form</i></b>. Will fill in as much as it can,
                    where you can preview or download the word file.
                </div>
            )}

            {hasData && (
                <>
                    {/* toolbar */}
                    <div className="sticky top-0 z-20 mb-4 rounded-xl border border-line bg-white/95 p-4 shadow-sm backdrop-blur">
                        <div className="flex flex-wrap items-center gap-3">
                            <div className="mr-auto">
                                <p className="font-display text-base font-bold text-ink">{fields.center_name || address}</p>
                                <p className="text-xs text-charcoal/70">
                                    {progress.filled} of {progress.total} fields filled
                                </p>
                            </div>
                            <label className="flex items-center gap-1.5 text-xs text-charcoal">
                                <input type="checkbox" checked={onlyEmpty} onChange={(e) => setOnlyEmpty(e.target.checked)} />
                                Show only empty
                            </label>
                            <button
                                onClick={renderPreview}
                                disabled={busy !== null}
                                className="rounded-lg border border-line px-4 py-2 text-sm font-semibold text-charcoal transition hover:bg-paper disabled:opacity-40"
                            >
                                {busy === "render" ? "Building..." : "Preview"}
                            </button>
                            <button
                                onClick={download}
                                disabled={busy !== null}
                                className="rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-ink-2 disabled:opacity-40"
                            >
                                {busy === "download" ? "Building..." : "Download .docx"}
                            </button>
                        </div>

                        {listings.length > 0 && (
                            <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
                                <span className="text-xs font-semibold text-charcoal">Listed space:</span>
                                <select
                                    value={listingId}
                                    onChange={(e) => applyListing(listings.find((l) => l.id === e.target.value) || null)}
                                    className="min-w-[280px] flex-1 rounded-lg border border-line bg-paper px-3 py-1.5 text-sm text-ink"
                                >
                                    <option value="">None - fill Section 2 by hand</option>
                                    {listings.map((l) => (
                                        <option key={l.id} value={l.id}>
                                            {l.summary}
                                            {l.distance_mi != null ? ` (${l.distance_mi} mi)` : ""}
                                        </option>
                                    ))}
                                </select>
                                {listing?.flyer_url && (
                                    <a href={listing.flyer_url} target="_blank" rel="noreferrer" className="text-xs text-sky underline">
                                        Flyer
                                    </a>
                                )}
                                {listing?.listing_url && (
                                    <a href={listing.listing_url} target="_blank" rel="noreferrer" className="text-xs text-sky underline">
                                        Listing
                                    </a>
                                )}
                            </div>
                        )}

                        <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                            {(Object.keys(SOURCE_STYLE) as FieldSource[]).map((s) => (
                                <span key={s} className={`rounded border px-1.5 py-0.5 ${SOURCE_STYLE[s].cls}`}>
                                    {SOURCE_STYLE[s].label}
                                </span>
                            ))}
                            <span className="text-charcoal/60">Badge shows where each value came from; edited values get a dot.</span>
                        </div>
                    </div>

                    {/* preview */}
                    {previewOpen && (
                        <div className="mb-6 rounded-xl border border-line bg-white shadow-sm">
                            <div className="flex items-center justify-between border-b border-line px-4 py-2">
                                <p className="text-sm font-semibold text-ink">Word preview</p>
                                <div className="flex gap-2">
                                    <button onClick={renderPreview} disabled={busy !== null} className="text-xs text-sky underline disabled:opacity-40">
                                        Refresh
                                    </button>
                                    <button onClick={() => setPreviewOpen(false)} className="text-xs text-charcoal underline">
                                        Close
                                    </button>
                                </div>
                            </div>
                            <div ref={previewRef} className="hb-docx-preview max-h-[80vh] overflow-auto bg-paper-dim" />
                            <style jsx global>{`
                                .hb-docx-preview .docx-wrapper {
                                    background: transparent;
                                    padding: 16px;
                                }
                            `}</style>
                        </div>
                    )}

                    {/* sections */}
                    <div className="space-y-3">
                        {schema.sections.map((sec) => {
                            const secFields = schema.fields.filter(
                                (f) => f.section === sec.id && (!onlyEmpty || !(fields[f.id] || "").trim())
                            );
                            const secTables = schema.tables.filter((t) => t.section === sec.id);
                            const hasSwot = schema.swot.section === sec.id;
                            if (!secFields.length && !secTables.length && !hasSwot) return null;
                            const open = openSections.has(sec.id);
                            const [done, total] = progress.bySection[sec.id] || [0, 0];
                            return (
                                <div key={sec.id} className="rounded-xl border border-line bg-white shadow-sm">
                                    <button
                                        onClick={() =>
                                            setOpenSections((s) => {
                                                const n = new Set(s);
                                                if (n.has(sec.id)) n.delete(sec.id);
                                                else n.add(sec.id);
                                                return n;
                                            })
                                        }
                                        className="flex w-full items-center justify-between px-4 py-3 text-left"
                                    >
                                        <span className="font-display text-sm font-bold text-ink">{sec.label}</span>
                                        <span className="text-xs text-charcoal/70">
                                            {total > 0 && `${done}/${total}`} {open ? "▴" : "▾"}
                                        </span>
                                    </button>
                                    {open && (
                                        <div className="border-t border-line px-4 py-4">
                                            <div className="grid gap-3 sm:grid-cols-2">
                                                {secFields.map((f) => {
                                                    const mt = meta[f.id];
                                                    const src = mt?.source || f.source;
                                                    return (
                                                        <label key={f.id} className={`text-sm ${f.kind === "long" ? "sm:col-span-2" : ""}`}>
                                                            <span className="mb-1 flex items-center gap-2">
                                                                <span className="font-medium text-charcoal">{f.label}</span>
                                                                <span className={`rounded border px-1.5 py-0.5 text-[10px] ${SOURCE_STYLE[src].cls}`}>
                                                                    {SOURCE_STYLE[src].label}
                                                                    {mt?.edited ? " •" : ""}
                                                                </span>
                                                            </span>
                                                            {f.kind === "long" ? (
                                                                <textarea
                                                                    value={fields[f.id] || ""}
                                                                    onChange={(e) => setField(f.id, e.target.value)}
                                                                    rows={Math.min(10, Math.max(3, (fields[f.id] || "").split("\n").length + 1))}
                                                                    className="w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                                                                />
                                                            ) : (
                                                                <input
                                                                    value={fields[f.id] || ""}
                                                                    onChange={(e) => setField(f.id, e.target.value)}
                                                                    className="w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                                                                />
                                                            )}
                                                            {(mt?.note || f.hint) && (
                                                                <span className="mt-1 block text-[11px] text-charcoal/60">{mt?.note || f.hint}</span>
                                                            )}
                                                        </label>
                                                    );
                                                })}
                                            </div>

                                            {secTables.map((spec) => (
                                                <TableEditor
                                                    key={spec.id}
                                                    spec={spec}
                                                    rows={tables[spec.id] || []}
                                                    onCell={(i, k, v) => setCell(spec, i, k, v)}
                                                    onAdd={() => addRow(spec)}
                                                    onRemove={(i) => removeRow(spec, i)}
                                                />
                                            ))}

                                            {hasSwot && (
                                                <div className="mt-2 grid gap-3 sm:grid-cols-2">
                                                    {schema.swot.quadrants.map((q) => (
                                                        <div key={q} className="rounded-lg border border-line bg-paper p-3">
                                                            <p className="mb-2 text-xs font-bold uppercase tracking-wide text-ink">{SWOT_LABELS[q]}</p>
                                                            {Array.from({ length: schema.swot.max_items }).map((_, i) => (
                                                                <input
                                                                    key={i}
                                                                    value={swot[q][i] || ""}
                                                                    onChange={(e) => setSwotItem(q, i, e.target.value)}
                                                                    placeholder={`${i + 1}.`}
                                                                    className="mb-1.5 w-full rounded border border-line bg-white px-2 py-1.5 text-sm text-ink outline-none focus:border-sky"
                                                                />
                                                            ))}
                                                        </div>
                                                    ))}
                                                    <p className="text-[11px] text-charcoal/60 sm:col-span-2">
                                                        Section 4&apos;s SWOT box and the A5 weakness/threat list are built from this grid when
                                                        they&apos;re left blank.
                                                    </p>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </>
            )}
        </section>
    );
});

export default HBSiteReview;

function TableEditor({
    spec,
    rows,
    onCell,
    onAdd,
    onRemove,
}: {
    spec: ReviewTableSpec;
    rows: TableRow[];
    onCell: (i: number, key: string, value: string) => void;
    onAdd: () => void;
    onRemove: (i: number) => void;
}) {
    const count = spec.fixed_rows ? spec.max_rows : Math.max(rows.length, 1);
    return (
        <div className="mt-4">
            <p className="mb-1 flex items-center gap-2 text-sm font-medium text-charcoal">
                {spec.label}
                <span className={`rounded border px-1.5 py-0.5 text-[10px] ${SOURCE_STYLE[spec.source].cls}`}>
                    {SOURCE_STYLE[spec.source].label}
                </span>
            </p>
            {spec.hint && <p className="mb-1 text-[11px] text-charcoal/60">{spec.hint}</p>}
            <div className="overflow-x-auto rounded-lg border border-line">
                <table className="w-full text-sm">
                    <thead className="bg-paper-dim text-left text-xs text-charcoal">
                        <tr>
                            {spec.row_labels && <th className="px-2 py-1.5">System</th>}
                            {spec.fixed_rows && !spec.row_labels && <th className="w-10 px-2 py-1.5">#</th>}
                            {spec.columns.map(([key, label]) => (
                                <th key={key} className="px-2 py-1.5">
                                    {label}
                                </th>
                            ))}
                            {!spec.fixed_rows && <th className="w-8" />}
                        </tr>
                    </thead>
                    <tbody>
                        {Array.from({ length: count }).map((_, i) => (
                            <tr key={i} className="border-t border-line">
                                {spec.row_labels && <td className="px-2 py-1 text-xs text-charcoal">{spec.row_labels[i]}</td>}
                                {spec.fixed_rows && !spec.row_labels && <td className="px-2 py-1 text-xs text-charcoal">{i + 1}</td>}
                                {spec.columns.map(([key]) => (
                                    <td key={key} className="p-1">
                                        <input
                                            value={rows[i]?.[key] || ""}
                                            onChange={(e) => onCell(i, key, e.target.value)}
                                            className="w-full rounded border border-transparent bg-transparent px-2 py-1 text-sm text-ink outline-none hover:border-line focus:border-sky focus:bg-white"
                                        />
                                    </td>
                                ))}
                                {!spec.fixed_rows && (
                                    <td className="p-1 text-center">
                                        <button onClick={() => onRemove(i)} className="text-xs text-charcoal/50 hover:text-danger" title="Remove row">
                                            ✕
                                        </button>
                                    </td>
                                )}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            {!spec.fixed_rows && rows.length < spec.max_rows && (
                <button onClick={onAdd} className="mt-1 text-xs font-semibold text-sky">
                    + Add row
                </button>
            )}
        </div>
    );
}