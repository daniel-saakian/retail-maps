"use client";
 
import { useState } from "react";
import { JobDetail, api } from "@/lib/api";
import StatusPill from "./StatusPill";
import LoadingScreen from "./LoadingScreen";
import { splitBrokerList, splitCommaList } from "@/lib/text";
 
const TABLE_HEADERS = [
    "Plaza / Property Name", "State", "County", "City", "Address",
    "# Anchors", "Anchor Names", "# Tenants", "Other Tenants", "Score",
    "Brokerage(s)", "Broker(s)", "Broker Contact(s)", "Broker URL(s)",
];
 
type Tab = "map" | "table" | "log";
 
export default function JobCard({
    job,
    onDismiss,
}: {
    job: JobDetail;
    onDismiss: (id:string) => void;
}) {
    const [tab, setTab] = useState<Tab>("map");
    const [downloading, setDownloading] = useState(false);
    const [cancelling, setCancelling] = useState(false);
    const inFlight = job.status === "queued" || job.status === "running";
 
    async function handleDownloadExcel() {
        setDownloading(true);
        try {
            await api.downloadExcel(job.id, job.display || job.city);
        } catch (e) {
            alert((e as Error).message);
        } finally {
            setDownloading(false);
        }
    }
 
    async function handleCancel() {
        setCancelling(true);
        try {
            await api.cancelSearch(job.id);
        } catch (e) {
            alert((e as Error).message);
            setCancelling(false);
        }
    }
 
    return (
        <div className="rounded-xl border border-line bg-white p-5 shadow-sm">
            <div className="flex items-start justify-between">
                <div>
                    <div className="flex items-center gap-3">
                        <h2 className="font-display text-lg font-bold text-ink">{job.city}</h2>
                        <StatusPill status={job.status} />
                    </div>
                    <p className="mt-0.5 font-mono text-xs text-charcoal">
                        started {new Date(job.created_at * 1000).toLocaleTimeString()}
                    </p>
                </div>
                <div className="flex shrink-0 gap-2">
                    {inFlight && (
                        <button
                            onClick={handleCancel}
                            disabled={cancelling}
                            className="rounded-md border border-danger px-3 py-1 text-xs font-medium text-danger hover:bg-danger/10 disabled:opacity-50"
                        >
                            {cancelling ? "Cancelling..." : "Cancel"}
                        </button>
                    )}
                    <button
                        onClick={() => onDismiss(job.id)}
                        className="rounded-md border border-line px-3 py-1 text-xs font-medium text-charcoal hover:bg-paper-dim"
                    >
                        Dismiss
                    </button>
                </div>
            </div>
 
            {inFlight && <LoadingScreen log={job.log} createdAt={job.created_at} />}
 
            {job.status === "error" && (
                <div className="mt-4 rounded-lg bg-danger/10 p-3 text-sm text-danger-dark">{job.error}</div>
            )}
            {job.status === "empty" && (
                <div className="mt-4 rounded-lg bg-brass/10 p-3 text-sm text-caution">
                    {job.reason || "No qualifying retail clusters found."}
                </div>
            )}
            {job.status === "cancelled" && (
                <div className="mt-4 rounded-lg bg-charcoal/10 p-3 text-sm text-charcoal">
                    Search cancelled before it finished.
                </div>
            )}
            
            {job.status === "done" && (
                <div className="mt-4">
                    <p className="mb-3 text-sm font-medium text-success">
                        {job.plazas?.length ?? 0} plaza(s) found near {job.display}
                    </p>
                    <div className="mb-3 flex gap-1 border-b border-line">
                        {(["map", "table", "log"] as Tab[]).map((t) => (
                            <button
                            key={t}
                            onClick={() => setTab(t)}
                            className={`rounded-t-lg px-4 py-2 text-xs font-semibold uppercase tracking-[0.08em] ${
                                tab === t
                                    ? "border-b-2 border-sky text-ink"
                                    : "text-charcoal/60 hover:text-charcoal"
                            }`}
                            >
                                {t}
                            </button>
                        ))}
                    </div>
                {tab === "map" && job.map_url && (
                    <iframe
                        src={job.map_url}
                        className="h-[600px] w-full rounded-lg border border-line"
                    />
                )}
 
                {tab === "table" && (
                    <div className="max-h-[420px] overflow-auto rounded-lg border border-line">
                        <table className="w-full text-left text-xs">
                            <colgroup>
                                {/* Plaza Name, State, County, City, Address, # Anchors, Anchor Names, # Tenants,
                                    # Tenants, Other Tenants, Score, Brokerage(s), Broker(s),
                                    Broker Contact(s), Broker URL(s) */}
                                <col style={{ width: "10%" }} />
                                <col style={{ width: "3%" }} />
                                <col style={{ width: "6%" }} />
                                <col style={{ width: "6%" }} />
                                <col style={{ width: "10%" }} />
                                <col style={{ width: "3%" }} />
                                <col style={{ width: "9%" }} />
                                <col style={{ width: "3%" }} />
                                <col style={{ width: "11%" }} />
                                <col style={{ width: "3%" }} />
                                <col style={{ width: "9%" }} />
                                <col style={{ width: "9%" }} />
                                <col style={{ width: "9%" }} />
                                <col style={{ width: "9%" }} />
                            </colgroup>
                            <thead className="sticky top-0 bg-ink text-paper">
                                <tr>
                                    {TABLE_HEADERS.map((h) => (
                                        <th key={h} className="whitespace-nowrap px-3 py-2 font-semibold">
                                            {h}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {job.plazas?.map((p, i) => (
                                    <tr key={i} className={i % 2 ? "bg-paper-dim/60" : "bg-white"}>
                                        <td className="align-top px-3 py-1.5 break-words font-medium text-ink">{p.name}</td>
                                        <td className="align-top px-3 py-1.5">{p.state}</td>
                                        <td className="align-top px-3 py-1.5 break-words">{p.county}</td>
                                        <td className="align-top px-3 py-1.5 break-words">{p.city}</td>
                                        <td className="align-top px-3 py-1.5 break-words">{p.address}</td>
                                        <td className="align-top px-3 py-1.5 font-mono">{p.num_anchors}</td>
                                        <td className="align-top px-3 py-1.5">
                                            {splitCommaList(p.anchor_names).map((item,j) => (
                                                <div key={j} className="break-words">{item}</div>
                                            ))}
                                        </td>
                                        <td className="align-top px-3 py-1.5 font-mono">{p.num_tenants}</td>
                                        <td className="align-top px-3 py-1.5">
                                            {splitCommaList(p.tenant_names).map((item, j) => (
                                                <div key={j} className="break-words">{item}</div>
                                            ))}
                                        </td>
                                        <td className="align-top px-3 py-1.5 font-mono">{p.score}</td>
                                        <td className="align-top px-3 py-1.5">
                                            {splitBrokerList(p.brokerages).map((item, j) => (
                                                <div key={j} className="break-words">{item}</div>
                                            ))}
                                        </td>
                                        <td className="align-top px-3 py-1.5">
                                            {splitBrokerList(p.brokers).map((item, j) => (
                                                <div key={j} className="break-words">{item}</div>
                                            ))}
                                        </td>
                                        <td className="align-top px-3 py-1.5">
                                            {splitBrokerList(p.broker_contacts).map((item,j) => (
                                                <div key={j} className="break-words font-mono">{item}</div>
                                            ))}
                                        </td>
                                        <td className="align-top px-3 py-1.5">
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
                {tab === "log" && (
                    <pre className="max-h-[420px] overflow-y-auto rounded-lg bg-ink p-3 font-mono text-xs text-paper">
                        {job.log.join("\n")}
                    </pre>
                )}
                <div className="mt-4 flex gap-3">
                    {job.excel_available && (
                        <button
                            onClick={handleDownloadExcel}
                            disabled={downloading}
                            className="rounded-lg bg-success px-4 py-2 text-sm font-semibold text-white hover:bg-success-dark disabled:opacity-50"
                        >
                            {downloading ? "Downloading..." : "Download Excel"}
                        </button>
                    )}
                    {job.map_url && (
                        <a
                            href={job.map_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="rounded-lg border border-line px-4 py-2 text-sm font-medium text-ink hover:bg-paper-dim"
                        >
                            Open map link
                        </a>
                    )}
                </div>
            </div>
            )}
        </div>
    );
}