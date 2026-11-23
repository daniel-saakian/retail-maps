"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
    api, ProjectionField, ProjectionInputs, ProjectionList, ProjectionMap as MapData, ProjectionRange,
    ProjectionResult, ProjectionSave, SourdoughResult, TggResult,
} from "@/lib/api";
import { defaultInputs, errorMessage, keyFromFullAddress, refreshProjections, setMark, useProjections } from "@/lib/projections";
import { timeAgo } from "@/lib/listings";
import ProjectionMap, { resolveMap } from "@/components/ProjectionMap";
import ProjectionInputFields from "@/components/ProjectionInputs";

const CONFIDENCES = ["75", "85", "90", "95"] as const;

type Rng = ProjectionRange & { short: string };

const isSourdough = (r: ProjectionResult): r is SourdoughResult => r.brand_kind === "sourdough";


interface View {
    ranges: Rng[];
    caption: string;
    scoreHint: string;
    chance: { label: string; value: string };
    extras: { label: string; value: string }[];
}

function view(r: ProjectionResult): View {
    if (isSourdough(r)) {
        const ranges = r.ranges.map((x) => ({ ...x, short: x.label }));
        const extras: View["extras"] = [];
        if (r.score_market != null) extras.push({ label: `Score within ${r.market}`, value: String(Math.round(r.score_market)) });
        if (r.chance_low) extras.push({ label: r.chance_low.label, value: `${r.chance_low.pct}%` });
        return {
            ranges,
            caption: r.held_out
                ? `On stores the model had not seen, ${r.held_out.holds_pct}% of actual sales fell inside the range (R² ${r.held_out.r2 != null ? r.held_out.r2.toFixed(2) : "n/a"}). Use the range, not a single figure.`
                : "Use the range, not a single figure, and treat the score as a ranking aid.",
            scoreHint: "Percentile of the predicted revenue against all existing stores (0–100).",
            chance: { label: r.chance?.label ?? "Chance of top third", value: r.chance ? `${r.chance.pct}%` : "n/a" },
            extras,
        };
    }
    const t = r as TggResult;
    return {
        ranges: CONFIDENCES.map((c) => ({
            id: c, label: `Aggressive ${c}%`, short: `${c}%`, headline: c === "75",
            weekly: t.intervals[c].weekly, annual: t.intervals[c].annual,
        })),
        caption: `Model honest cross-validation R² is ${t.model_r2 >= 0 ? "+" : ""}${t.model_r2.toFixed(2)}: use the range, not a single figure, and treat the score as a ranking aid.`,
        scoreHint: "Percentile of the predicted revenue against all existing stores (0–100).",
        chance: { label: "Chance of top 10", value: `${t.top10_pct}%` },
        extras: [],
    };
}

const money = (n: number) => `$${Math.round(n).toLocaleString()}`;
const FLAG_TEXT: Record<string, string> = {
    close_to_competitor: "A direct competitor is very close to this site. Treat the low end of the range as the likelier outcome.",
    demographics_estimated: "Some demographic inputs couldn't be looked up for this address and were estimated from the portfolio average.",
};

function isBusy(s: ProjectionSave) {
    return s.status === "pending" || s.status === "running";
}

export default function ProjectionsPage() {
    const { loaded, brands, marks, hasAccess } = useProjections();
    const [brand, setBrand] = useState<string | null>(null);
    const [list, setList] = useState<ProjectionList | null>(null);
    const [selected, setSelected] = useState<string | null>(null);
    const [loadError, setLoadError] = useState<string | null>(null);
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        if (!brand && brands.length) setBrand(brands[0].id);
    }, [brands, brand]);

    const load = useCallback(async (b: string) => {
        try {
            const data = await api.listProjections(b);
            setList(data);
            setLoadError(null);
            return data;
        } catch (e) {
            setLoadError(errorMessage(e));
            return null;
        }
    }, []);


    useEffect(() => {
        if (!brand) return;
        let cancelled = false;
        const tick = async () => {
            const data = await load(brand);
            if (cancelled) return;
            if (data?.saves.some(isBusy)) timer.current = setTimeout(tick, 4000);
        };
        setList(null);
        setSelected(null);
        void tick();
        return () => {
            cancelled = true;
            if (timer.current) clearTimeout(timer.current);
        };
    }, [brand, load]);

    const restartPolling = useCallback(async () => {
        if (!brand) return;
        if (timer.current) clearTimeout(timer.current);
        const data = await load(brand);
        if (data?.saves.some(isBusy)) {
            timer.current = setTimeout(function tick() {
                load(brand).then((d) => { if (d?.saves.some(isBusy)) timer.current = setTimeout(tick, 4000); });
            }, 4000);
        }
    }, [brand, load]);

    const saves = useMemo(() => list?.saves ?? [], [list]);
    const current = saves.find((s) => s.id === selected) ?? saves[0] ?? null;

    if (loaded && !hasAccess) {
        return (
            <main className="mx-auto max-w-3xl px-6 py-16 text-center">
                <h1 className="font-display text-2xl font-bold text-ink">Projections</h1>
                <p className="mt-3 text-charcoal">Your account doesn&apos;t have access to any brand projections yet.</p>
            </main>
        )
    }

    const brandLabel = brands.find((b) => b.id === brand)?.label ?? "";

    return (
        <main className="mx-auto max-w-6xl px-6 py-8">
            <header className="flex flex-wrap items-end justify-between gap-4">
                <div>
                    <h1 className="font-display text-3xl font-bold text-ink">Projections</h1>
                    <p className="mt-1 max-w-xl text-sm text-charcoal">
                        Sales projections for saved addresses.

                    </p>
                </div>
                {brands.length > 1 ? (
                    <div className="flex gap-1 rounded-lg border border-line bg-white p-1" role="tablist">
                        {brands.map((b) => (
                            <button
                                key={b.id}
                                role="tab"
                                aria-selected={brand === b.id}
                                onClick={() => setBrand(b.id)}
                                className={`rounded-md px-3 py-1.5 text-sm font-semibold transition ${
                                    brand === b.id ? "bg-ink text-white" : "text-charcoal hover:bg-ink/5"
                                }`}
                            >
                                {b.label}
                            </button>
                        ))}
                    </div>
                ) : (
                    brandLabel && (
                        <span className="rounded-full bg-ink/5 px-3 py-1 text-xs font-semibold uppercase tracking-[0.1em] text-ink">
                            {brandLabel}
                        </span>
                    )
                )}
            </header>

            <div className="mt-6 grid gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
                <aside className="min-w-0 space-y-4">
                    {list && brand && (
                        <AddAddress
                            brand={brand}
                            label={list.label}
                            fields={list.fields}
                            marks={marks}
                            onAdded={(id) => { setSelected(id); void restartPolling(); void refreshProjections(); }}
                        />
                    )}
                    <SavedList
                        saves={saves}
                        loading={!list && !loadError}
                        error={loadError}
                        selectedId={current?.id ?? null}
                        onSelect={setSelected}
                    />
                </aside>

                <section className="min-w-0">
                    {current ? (
                        <Detail
                            key={current.id}
                            save={current}
                            label={brandLabel}
                            fields={list?.fields ?? []}
                            onChanged={() => { void restartPolling(); }}
                            onRemoved={() => { setSelected(null); void restartPolling(); void refreshProjections(); }}
                        />
                    ) : (
                        list && (
                            <div className="rounded-lg border border-dashed border-line bg-white px-6 py-16 text-center text-sm text-charcoal">
                                Nothing saved under {brandLabel} yet.
                            </div>
                        )
                    )}
                </section>
            </div>
        </main>
    );
}



function AddAddress({
    brand, label, fields, marks, onAdded,
}: { brand: string; label: string; fields: ProjectionField[]; marks: Record<string, string[]>; onAdded: (id: string) => void; }) {
    const [address, setAddress] = useState("");
    const [inputs, setInputs] = useState<ProjectionInputs>(() => defaultInputs(fields));
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        const full = address.trim();
        if (full.length < 8) { setError("Enter a full address, e.g. 123 Main St, Sacramento, CA"); return; }
        setBusy(true);
        setError(null);
        try {
            const parts = full.split(",").map((p) => p.trim());
            const key = keyFromFullAddress(full);

            const res = await setMark({
                key, address: full,
                city: parts[1] || null,
                state: parts[2]?.split(/\s+/)[0] || null,
                source: "manual",
                brands: Array.from(new Set([...(marks[key] || []), brand])),
                inputs: {[brand]: inputs},
            });
            const row = res.saves.find((s) => s.brand === brand);
            setAddress("");
            if (row) onAdded(row.id);
        } catch(err) {
            setError(errorMessage(err));
        } finally {
            setBusy(false);
        }
    };

    return (
        <form onSubmit={submit} className="rounded-lg border border-line bg-white p-4">
            <label htmlFor="proj-address" className="text-[11px] font-semibold uppercase tracking-[0.1em] text-charcoal">
                Add an address · {label}
            </label>
            <input
                id="proj-address"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="123 Main St, Sacramento, CA"
                className="mt-2 w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink placeholder:text-charcoal/50 focus:border-sky focus:outline-none focus:ring-2 focus:ring-sky/20"
            />
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-charcoal">
                <ProjectionInputFields fields={fields} value={inputs} onChange={setInputs} label={label} />
            </div>
            {error && <p className="mt-2 text-xs text-danger">{error}</p>}
            <button
                type="submit"
                disabled={busy}
                className="mt-2 w-full rounded-lg bg-ink px-3 py-2 text-sm font-semibold text-white transition hover:bg-ink/90 disabled:opacity-50"
            >
                {busy ? "Adding..." : "Run projection"}
            </button>
        </form>
    );
}



function SavedList({
    saves, loading, error, selectedId, onSelect,
}: {
    saves: ProjectionSave[]; loading: boolean; error: string | null;
    selectedId: string | null; onSelect: (id: string) => void;
}) {
    return (
        <div className="rounded-lg border border-line bg-white">
            <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
                <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-charcoal">Saved</span>
                <span className="text-xs text-charcoal/70">{saves.length}</span>
            </div>
            {error && <p className="px-4 py-3 text-sm text-danger">{error}</p>}
            {loading && <p className="px-4 py-6 text-sm text-charcoal">Loading...</p>}
            <ul className="max-h-[28rem] divide-y divide-line overflow-y-auto">
                {saves.map((s) => {
                    const r = s.result;
                    const active = s.id === selectedId;
                    return (
                        <li key={s.id}>
                            <button
                                onClick={() => onSelect(s.id)}
                                className={`flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition ${
                                    active ? "bg-sky/10": "hover:bg-paper"
                                }`}
                            >
                                <div className="min-w-0">
                                    <div className="truncate text-sm font-semibold text-ink">{s.name || s.address}</div>
                                    <div className="truncate text-xs text-charcoal">
                                        {s.name ? s.address : ""}
                                        {s.name ? " · " : ""}
                                        {s.source === "digest" ? "From digest" : "Added manually"}
                                    </div>
                                </div>
                                <div className="shrink-0 text-right">
                                    {s.status === "done" && r ? (
                                        <>
                                            <div className="font-display text-lg font-bold leading-none text-ink">{Math.round(r.score)}</div>
                                            <div className="mt-0.5 text-[10px] uppercase tracking-wider text-charcoal/70">score</div>
                                        </>
                                    ) : s.status === "error" ? (
                                        <span className="test-xs font-semibold text-danger">Failed</span>
                                    ) : (
                                        <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-sky">
                                            <span className="h-1.5 w-1.5 animate-pulse roudned-full bg-sky" />
                                            Running
                                        </span>
                                    )}
                                </div>
                            </button>
                        </li>
                    );
                })}
            </ul>
        </div>
    );
}



function Detail({
    save, label, fields, onChanged, onRemoved,
}: {
    save: ProjectionSave; label: string; fields: ProjectionField[];
    onChanged: () => void; onRemoved: () => void;
}) {
    const [sel, setSel] = useState<string | null>(null);
    const [inputs, setInputs] = useState<ProjectionInputs>({ ...defaultInputs(fields), ...save.inputs });
    const [busy, setBusy] = useState(false);
    const[confirmRemove, setConfirmRemove] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const r=save.result;
    const v=r ? view(r) : null;
    const rng = v ? (v.ranges.find((x) => x.id === sel) ?? v.ranges.find((x) => x.headline) ?? v.ranges[0]) : null;
    const saved = { ...defaultInputs(fields), ...save.inputs };
    const dirty = fields.some((f) => inputs[f.id] !== saved[f.id]);

    const rerun = async () => {
        setBusy(true);
        setError(null);
        try {
            await api.rerunProjection(save.id, { inputs });
            onChanged();
        } catch (e) {
            setError(errorMessage(e));
        } finally {
            setBusy(false);
        }
    };

    const remove = async () => {
        setBusy(true);
        try {
            await api.deleteProjection(save.id);
            onRemoved();
        } catch (e) {
            setError(errorMessage(e));
            setBusy(false);
        }
    };
    
    return (
        <div className="rounded-lg border border-line bg-white">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-6 py-5">
                <div className="min-w-0">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-charcoal">{label} projection</div>
                    <h2 className="mt-1 font-display text-2xl font-bold text-ink">{save.name || r?.matched_address|| save.address}</h2>
                    <p className="mt-0.5 text-sm text-charcoal">
                        {r ? (
                            <a
                                href={`https://www.google.com/maps/search/?api=1&query=${r.lat},${r.lon}`}
                                target = "_blank"
                                rel = "noopener noreferrer"
                                className="hover:text-sky hover:underline"
                            >
                                {r.matched_address}
                            </a>
                        ) : save.address}
                    </p>
                    <p className="mt-1 text-xs text-charcoal/70">
                        {save.source === "digest" ? "Saved from the digest" : "Added manually"}
                        {save.saved_by_email ? `by ${save.saved_by_email.split("@")[0]}` : ""} · {timeAgo(save.created_at)}
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    {confirmRemove ? (
                        <>
                            <span className="text-xs text-charcoal">Remove this projection</span>
                            <button onClick={remove} disabled={busy} className="rounded-lg bg-danger px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50">
                                Remove
                            </button>
                            <button onClick={() => setConfirmRemove(false)} className="rounded-lg px-3 py-1.5 text-xs font-semibold text-charcoal hover:bg-ink/5">
                                Keep
                            </button>
                        </>
                    ) : (
                        <button onClick={() => setConfirmRemove(true)} className="rounded-lg px-3 py-1.5 text-xs font-semibold text-charcoal hover:bg-ink/5">
                            Remove
                        </button>
                    )}
                </div>
            </div>

            {isBusy(save) && (
                <div className="px-6 py-14 text-center">
                    <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-line border-t-sky" />
                    <p className="mt-4 text-sm font-medium text-ink">Running the projection...</p>
                    <p className="mx-auto mt-1 max-w-sm text-xs text-charcoal">
                        This usually takes under a minute...

                    </p>
                </div>    
            )}

            {save.status === "error" && (
                <div className="px-6 py-10">
                    <p className="text-sm font-semibold text-danger">{save.error || "The projection failed."}</p>
                    <div className="mt-4 flex flex-wrap items-center gap-3">
                        <button onClick={rerun} disabled={busy} className="rounded-lg bg-ink px-4 py-2 text-sm font-semibold text-white hover:bg-ink/90 disabled:opacity-50">
                            {busy ? "Starting..." : "Re-run"}
                        </button>
                    </div>
                    {error && <p className="mt-2 text-xs text-danger">{error}</p>}
                </div>
            )}

            {save.status === "done" && r && v && rng && (
                <div className="px-6 py-6">
                    <p className="text-sm text-charcoal">{v.caption}</p>

                    <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
                        <span className="text-[11px] font-semibold uppercase tracking-[0.1em] text-charcoal">
                            {rng.label} range{rng.headline ? " (headline)" : ""}
                        </span>
                        <RangePicker ranges={v.ranges} sel={rng.id} setSel={setSel} />
                    </div>

                    <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        <Kpi big label={`Weekly predicted range (${rng.short})`} value={`${money(rng.weekly[0])} – ${money(rng.weekly[1])}`} />
                        <Kpi big label={`Annual predicted revenue range (${rng.short})`} value={`${money(rng.annual[0])} – ${money(rng.annual[1])}`} />
                        <Kpi big label="Site score" value={String(Math.round(r.score))} hint={v.scoreHint} accent />
                        <Kpi big label={v.chance.label} value={v.chance.value} />
                    </div>
                    {v.extras.length > 0 && (
                        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                            {v.extras.map((x) => <Kpi key={x.label} label={x.label} value={x.value} />)}
                        </div>
                    )}

                    <RangeBars ranges={v.ranges} sel={rng.id} />

                    {isSourdough(r) ? (
                        r.notes.length > 0 && (
                            <ul className="mt-4 space-y-2 rounded-lg border border-caution/10 px-4 py-3 text-sm text-ink">
                                {r.notes.map((n, i) => <li key={i}>{n}</li>)}
                            </ul>
                        )
                    ) : (
                        r.flags.map((f) => FLAG_TEXT[f] && (
                            <p key={f} className="mt-4 rounded-lg border border-caution/30 bg-caution/10 px-4 py-3 text-sm text-ink">
                                {FLAG_TEXT[f]}
                            </p>
                        ))
                    )}

                    {r.map && (
                        <div className="mt-8 border-t border-line pt-6">
                            <h3 className="mb-3 font-display text-lg font-bold text-ink">Map</h3>
                            <ProjectionMap
                                map={r.map}
                                lat={r.lat}
                                lon={r.lon}
                                siteTip={`<b>This site</b><br/>Score: ${Math.round(r.score)}/100 (percentile vs portfolio)<br/>${money(rng.annual[0])} - ${money(rng.annual[1])} / yr (${rng.label})`}
                            />
                        </div>
                    )}

                    {isSourdough(r) ? <Facts facts={r.facts} /> : r.nearby && <AroundSite near={r.nearby} />}

                    {r.map && <NearbyTable map={r.map} brandLabel={label} />}

                    {!isSourdough(r) && r.drivers.length > 0 && (
                        <div className="mt-8 border-t border-line pt-6">
                            <h3 className="font-display text-lg font-bold text-ink">What&apos;s moving the number</h3>
                            <ul className="mt-3 space-y-2.5">
                                {r.drivers.map((d) => (
                                    <li key={d.label} className="grid grid-cols-[minmax(0,12rem)_1fr_2.5rem] items-center gap-3 text-sm">
                                        <span className="truncate text-ink">{d.label}</span>
                                        <span className="h-2 rounded-full bg-ink/5">
                                            <span
                                                className={`block h-2 rounded-full ${d.direction === "up" ? "bg-success" : "bg-danger"}`}
                                                style={{ width: `${Math.max(d.share_pct, 3)}%` }}
                                            />
                                        </span>
                                        <span className={`text-right text-xs font-semibold ${d.direction === "up" ? "text-success-dark" : "text-danger"}`}>
                                            {d.direction === "up" ? "↑" : "↓"} {d.share_pct}%
                                        </span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    <div className="mt-8 flex flex-wrap items-center gap-x-4 gap-y-3 border-t border-line pt-5 text-sm">
                        <span className="text-xs font-semibold uppercase tracking-[0.1em] text-charcoal">Assumes</span>
                        <ProjectionInputFields fields={fields} value={inputs} onChange={setInputs} label={label} size="sm" />
                        <button
                            onClick={rerun}
                            disabled={!dirty || busy}
                            className="rounded-lg bg-ink px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-ink/90 disabled:opacity-30"
                        >
                            {busy ? "Starting..." : "Re-run"}
                        </button>
                        {error && <span className="text-xs text-danger">{error}</span>}
                    </div>
                </div>
            )}
        </div>
    );
}



const NEARBY_ROWS: [string, string][] = [
    ["Grocers + big-box stores within 5 mi", "grocers_bigbox_within"],
    ["   Premium grocers", "premium_grocers"],
    ["   Conventional grocers", "conventional_grocers"],
    ["   Discount grocers", "discount_grocers"],
    ["   Warhouse clubs", "warehouse_clubs"],
    ["   Walmart", "walmart_grocers"],
    ["CAVA locations within 15 mi", "cava_within_15_mi"],
];

function pick(near: Record<string, string | number | null>, prefix: string): string | number | null | undefined {
    const k = Object.keys(near).find((x) => x.startsWith(prefix));
    return k === undefined ? undefined : near[k];
}

function AroundSite({ near }: { near: Record<string, string | number | null>}) {
    const nn = pick(near, "cava_nearest_mi");
    const rows: [string, string][] = [
        ...NEARBY_ROWS.map(([label, prefix]) => [label, String(pick(near,prefix) ?? 0)] as [string,string]),
        ["Nearest CAVA", typeof nn === "number" ? `{nn.toFixed(1)} mi` : "n/a"],
        ["Nearest direct competitor (any, incl. no sales data)", String(pick(near, "nearest_direct_competitor") ?? "none found")],
        ["Other Mediterranean concepts within 1 mi", String(pick(near, "nosales_mediterranean") ?? 0)],
        [
            "Direct competitors within 0.5 / 0.5 / 1 mi",
            `${pick(near, "direct_competitors_within_025mi") ?? 0} / ${pick(near, "direct_competitors_within_05mi") ?? 0} / ${pick(near, "direct_competitors_within_1mi") ?? 0}`,
        ],
    ];
    return (
        <div className="mt-8 border-t border-line pt-6">
            <h3 className="font-display text-lg font-bold text-ink">Around this site</h3>
            <div className="mt-3 overflow-x-auto rounded-lg border border-line">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="bg-paper text-left text-[11px] uppercase tracking-[0.1em] text-charcoal">
                            <th className="px-4 py-2 font-semibold" />
                            <th className="px-4 py-2 font-semibold">Count</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                        {rows.map(([a,b]) => (
                            <tr key={a}>
                                <td className="whitespace-pre px-4 py-2 text-ink">{a}</td>
                                <td className="px-4 py-2 text-charcoal">{b}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            <p className="mt-3 text-sm text-ink">
                <b>Grocer / big-box brands within 5 mi:</b> {String(pick(near, "grocer_brands_within") ?? "none")}
            </p>
            <p className="mt-1 text-sm text-ink">
                <b>Nearest grocer / big-box:</b> {String(pick(near, "nearest_grocer") ?? "n/a")}
            </p>
        </div>
    );
}

function NearbyTable({ map, brandLabel }: { map: MapData; brandLabel: string }) {
    const { cats } = resolveMap(map);
    const rows = [...map.points].sort((a,b) => a.mi - b.mi);
    const download = () => {
        const esc = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`;
        const lines = [
            ["Brand", "Category", "Distance (mi)", "Rank", "Revenue", "Latitude", "Longitude"].map(esc).join(","),
            ...rows.map((p) => [p.brand, cats[p.cat]?.label ?? p.cat, p.mi, p.rank, p.revenue, p.lat, p.lon].map(esc).join(",")),
        ];
        const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
        const a = document.createElement("a");
        a.href = url;
        a.download = `${brandLabel.toLowerCase()}-nearby-locations.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };
    return (
        <div className="mt-8 border-t border-line pt-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="font-display text-lg font-bold text-ink">Nearby locations within {map.radius_mi} miles ({rows.length})</h3>
                <button onClick={download} className="rounded-lg border border-line px-3 py-1.5 text-xs font-semibold text-ink hover:bg-paper">
                    Download nearby locations (CSV)
                </button>
            </div>
            <div className="mt-3 max-h-96 overflow-auto rounded-lg border border-line">
                <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-paper text-left text-[11px] uppercase tracking-[0.1em] text-charcoal">
                        <tr>
                            {["Brand", "Category", "Distance (mi)", "Rank", "Revenue"].map((h) => (
                                <th key={h} className="whitespace-nowrap px-4 py-2 font-semibold">{h}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                        {rows.map((p, i) => (
                            <tr key={i}>
                                <td className="whitespace-nowrap px-4 py-2 font-medium text-ink">{p.brand}</td>
                                <td className="whitespace-nowrap px-4 py-2 text-charcoal">{cats[p.cat]?.label ?? p.cat}</td>
                                <td className="px-4 py-2 text-charcoal">{p.mi}</td>
                                <td className="whitespace-nowrap px-4 py-2 text-charcoal">{p.rank}</td>
                                <td className="whitespace-nowrap px-4 py-2 text-charcoal">${p.revenue}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function RangePicker({ ranges, sel, setSel }: { ranges: Rng[]; sel: string; setSel: (id: string) => void }) {
    return (
        <div className="flex flex-wrap gap-1 rounded-lg border border-line p-0.5" role="group" aria-label="Confidence">
            {ranges.map((x) => (
                <button
                    key={x.id}
                    onClick={() => setSel(x.id)}
                    aria-pressed={sel === x.id}
                    className={`rounded-md px-2.5 py-1 text-xs font-semibold transition ${
                        sel === x.id ? "bg-ink text-white" : "text-charcoal hover:bg-ink/5"
                    }`}
                >
                    {x.short}
                </button>
            ))}
        </div>
    );
}


function Facts({ facts }: {facts: { label: string; value: string }[] }) {
    if (!facts.length) return null;
    return (
        <div className="mt-8 border-t border-line pt-6">
            <h3 className="font-display text-lg font-bold text-ink">Around this site</h3>
            <div className="mt-3 overflow-x-auto rounded-lg border border-line">
                <table className="w-full text-sm">
                    <tbody className="divide-y divide-line">
                        {facts.map((f) => (
                            <tr key={f.label}>
                                <td className="px-4 py-2 text-ink">{f.label}</td>
                                <td className="px-4 py-2 text-charcoal">{f.value}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

function Kpi({ label, value, hint, accent, big}: { label: string; value: string; hint?: string; accent?: boolean; big?: boolean }) {
    return (
        <div className="min-w-0 rounded-lg border border-line bg-paper px-4 py-3">
            <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-charcoal">{label}</div>
            <div className={`mt-1 font-display font-bold ${big ? "text-2xl" : "text-xl"} ${accent ? "text-sky" : "text-ink"}`}>{value}</div>
            {hint && <div className="mt-0.5 text-xs text-charcoal/70">{hint}</div>}
        </div>
    );
}

function RangeBars({ ranges, sel }: { ranges: Rng[]; sel: string }) {
    const sorted=[...ranges].sort((a, b) => (b.weekly[1] - b.weekly[0]) - (a.weekly[1] - a.weekly[0]));
    const lo = Math.min(...sorted.map((x) => x.weekly[0]));
    const hi = Math.max(...sorted.map((x) => x.weekly[1]));
    const span = hi - lo || 1;
    const pos = (n: number) => `${Math.min(100, Math.max(0, ((n - lo) / span) * 100))}%`;

    return (
        <div className="mt-5">
            <div className="relative h-3 rounded-full bg-ink/5">
                {sorted.map((x, i) => {
                    const [a,b] = x.weekly;
                    return (
                        <span
                            key={x.id}
                            className="absolute top-0 h-3 rounded-full bg-sky transition-all"
                            style={{ left: pos(a), width: `calc(${pos(b)} - ${pos(a)})`, opacity: x.id === sel ? 0.7 : 0.1 + i * 0.05 }}
                        />
                    );
                })}
            </div>
        </div>
    );
}