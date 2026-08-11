"use client";
 
import { useEffect, useState } from "react";
import { HistoryDetail, HistoryRun, api } from "@/lib/api";
import { splitBrokerList, kmToMiles } from "@/lib/text";
import { useJobs } from "@/lib/JobsContext";
 
export default function HistoryPage() {
    const { historyRuns, historyLoaded, historyLoading, historyError, refreshHistory } = useJobs();
    const [query, setQuery] = useState("");

    const filtered = historyRuns.filter((r) =>
        r.display.toLowerCase().includes(query.toLowerCase())
    );
 
    return (
        <main className="mx-auto max-w-6xl px-6 py-10">
            <header className="mb-8">
                <h1 className="font-display text-3xl font-bold text-ink">Search History</h1>
                <div className="wedge-divider mt-3 mb-2 max-w-xs">
                    <span className="whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.18em] text-charcoal">
                        Archive
                    </span>
                </div>
                <div className="flex items-center justify-between gap-3">
                    <p className="text-sm text-charcoal">
                        Every city that's been searched before, with its saved map and spreadsheet.
                    </p>
                    <button
                        onClick={() => refreshHistory()}
                        disabled={historyLoading}
                        className="shrink-0 text-xs font-semibold uppercase tracking-[0.08em] text-charcoal hover:text-ink disabled:opacity-50"
                    >
                        {historyLoading ? "Refreshing...": "Refresh"}
                    </button>
                </div>
            </header>
 
            <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Filter by city..."
                className="mb-5 w-full max-w-sm rounded-lg border border-line bg-white px-4 py-2.5 text-sm text-ink outline-none placeholder:text-charcoal/50 focus:border-sky focus:ring-1 focus:ring-sky"
            />
 
            {!historyLoaded && historyLoading && <p className="text-sm text-charcoal">Loading history...</p>}
            {historyError && (
                <p className="mb-4 rounded-lg bg-danger/10 p-3 text-sm text-danger-dark">{historyError}</p>
            )}
 
            {historyLoaded && filtered.length === 0 && (
                <p className="rounded-lg border border-dashed border-line bg-paper-dim/50 p-6 text-center text-sm text-charcoal/70">
                    No past runs match that search.
                </p>
            )}
 
            <div className="flex flex-col gap-3">
                {filtered.map((r) => (
                    <HistoryRowCard key={r.id} run={r} />
                ))}
            </div>
        </main>
    );
}
 
function HistoryRowCard({ run }: { run: HistoryRun }) {
    const [expanded, setExpanded] = useState(false);
    const [detail, setDetail] = useState<HistoryDetail | null>(null);
    const [detailError, setDetailError] = useState<string | null>(null);
    const [loadingDetail, setLoadingDetail] = useState(false);
    const [downloading, setDownloading] = useState(false);
 
    async function toggleExpand() {
        const next = !expanded;
        setExpanded(next);
        if (next && !detail) {
            setLoadingDetail(true);
            try {
                setDetail(await api.getHistoryRun(run.id));
            } catch (e) {
                setDetailError((e as Error).message);
            } finally {
                setLoadingDetail(false);
            }
        }
    }
 
    async function handleDownload() {
        setDownloading(true);
        try {
            await api.downloadHistoryExcel(run.id, run.display);
        } catch (e) {
            alert((e as Error).message);
        } finally {
            setDownloading(false);
        }
    }
 
    return (
        <div className="rounded-xl border border-line bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between gap-3">
                <button onClick={toggleExpand} className="min-w-0 flex-1 text-left">
                    <p className="truncate font-display font-semibold text-ink">{run.display}</p>
                    <p className="mt-0.5 font-mono text-xs text-charcoal">
                        {new Date(run.ran_at).toLocaleDateString()} · {run.plaza_count} plaza(s) ·{" "}
                        {kmToMiles(run.radius_km)} mi radius
                    </p>
                </button>
                <div className="flex shrink-0 gap-2">
                    {run.map_url && (
                        <a
                            href={run.map_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink hover:bg-paper-dim"
                        >
                            View map
                        </a>
                    )}
                    {run.excel_available && (
                        <button
                            onClick={handleDownload}
                            disabled={downloading}
                            className="rounded-lg bg-success px-3 py-1.5 text-xs font-semibold text-white hover:bg-success-dark disabled:opacity-50"
                        >
                            {downloading ? "Downloading..." : "Download Excel"}
                        </button>
                    )}
                    <button
                        onClick={toggleExpand}
                        className="rounded-lg border border-line px-3 py-1.5 text-xs font-medium text-ink hover:bg-paper-dim"
                    >
                        {expanded ? "Hide details" : "Details"}
                    </button>
                </div>
            </div>
 
            {expanded && (
                <div className="mt-4 border-t border-line pt-4">
                    {loadingDetail && <p className="text-sm text-charcoal">Loading plazas...</p>}
                    {detailError && <p className="text-sm text-danger-dark">{detailError}</p>}
                    {detail && (
                        <div className="max-h-72 overflow-auto rounded-lg border border-line">
                            <table className="w-full text-left text-xs">
                                <thead className="sticky top-0 bg-ink text-paper">
                                    <tr>
                                        {["Plaza", "County", "City", "Anchors", "Tenants", "Score", "Brokerage(s)", "Broker(s)", "Broker URL(s)"].map((h) => (
                                            <th key={h} className="whitespace-nowrap px-3 py-2 font-semibold">
                                                {h}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {detail.plazas.map((p, i) => (
                                        <tr key={i} className={i % 2 ? "bg-paper-dim/60" : "bg-white"}>
                                            <td className="px-3 py-1.5 align-top font-medium text-ink">{p.name}</td>
                                            <td className="px-3 py-1.5 align-top">{p.county}</td>
                                            <td className="px-3 py-1.5 align-top">{p.city}</td>
                                            <td className="px-3 py-1.5 align-top font-mono">{p.num_anchors}</td>
                                            <td className="px-3 py-1.5 align-top font-mono">{p.num_tenants}</td>
                                            <td className="px-3 py-1.5 align-top font-mono">{p.score}</td>
                                            <td className="px-3 py-1.5 align-top">
                                                {splitBrokerList(p.brokerages).map((item, j) => (
                                                    <div key={j} className="break-words">{item}</div>
                                                ))}
                                            </td>
                                            <td className="px-3 py-1.5 align-top">
                                                {splitBrokerList(p.brokers).map((item, j) => (
                                                    <div key={j} className="break-words">{item}</div>
                                                ))}
                                            </td>
                                            <td className="px-3 py-1.5 align-top">
                                                {splitBrokerList(p.broker_urls).map((item, j) => (
                                                    <a
                                                        key={j}
                                                        href={item}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="block truncate text-sky hover:underline"
                                                    >
                                                        {item}
                                                    </a>
                                                ))}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}