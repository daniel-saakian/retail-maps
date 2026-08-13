"use client";
 
import { useEffect, useMemo, useState } from "react";
 
type Stage = {
    match: RegExp;
    label: string;
    messages: string[];
};
 
const STAGES: Stage[] = [
    {
        match: /\[1\/6\]/,
        label: "Geocoding City",
        messages: ["Pinning down the city center...", "Resolving coordinates and FIPS codes..."],
    },
    {
        match: /\[2\/6\]/,
        label: "Scanning OpenStreetMap",
        messages: ["Querying OpenStreetMap for stores...", "Collecting shops and anchors nearby..."],
    },
    {
        match: /\[3\/6\]/,
        label: "Naming Retail Areas",
        messages: ["Matching Plazas to their retail names...", "Filtering out the unnamed strip malls..."],
    },
    {
        match: /\[4\/6\]/,
        label: "Building Plazas",
        messages: ["Grouping Stores into Shopping centers...", "Counting anchors and tenants per plaza..."],
    },
    {
        match: /\[5\/6\]/,
        label: "Scoring Plazas",
        messages: ["Looking up county lines...", "Scoring each plaza's retail strength..."],
    },
    {
        match: /\[6\/6\]/,
        label: "Finding brokers",
        messages: ["Crawling brokerage listings pages...", "Extracting broker names and contacts..."],
    }
];
 
const STARTING_MESSAGES = ["Spinning up the search...", "Getting coordinates in order..."];
 
function currentStageIndex(log: string[]): number {
    let idx = -1;
    for (const line of log) {
        for (let i=0; i < STAGES.length; i++) {
            if (STAGES[i].match.test(line)) idx = Math.max(idx, i);
        }
    }
    return idx;
}
 
function formatElapsed(seconds: number): string {
    const total = Math.max(0, Math.floor(seconds));
    const m = Math.floor(total / 60);
    const s = total % 60;
    return `${m}:${s.toString().padStart(2,"0")}`;
}
 
export default function LoadingScreen({
    log,
    createdAt,
}: {
    log: string[];
    createdAt: number;
}) {
    const stageIdx = useMemo(() => currentStageIndex(log), [log]);
    const stage = stageIdx >= 0 ? STAGES[stageIdx] : null;
    const messages = stage ? stage.messages : STARTING_MESSAGES;
 
    const [msgIdx, setMsgIdx] = useState(0);
    const [elapsed, setElapsed] = useState(() => Date.now() / 1000 - createdAt);
    const [detailsOpen, setDetailsOpen] = useState(false);
 
    useEffect(() => {
        setMsgIdx(0);
        const interval = setInterval(() => {
            setMsgIdx((i) => (i+1) % messages.length);
        }, 3600);
        return () => clearInterval(interval);
    }, [stageIdx]);
    
    useEffect(() => {
        const interval = setInterval(() => {
            setElapsed(Date.now() / 1000 - createdAt);
        }, 1000);
        return () => clearInterval(interval);
    }, [createdAt]);
 
    const stageNumber = Math.max(stageIdx + 1, 1);
    const progressPct = Math.max(8, Math.min(100, (stageNumber / STAGES.length) * 100));
 
    return (
        <div className="mt-4 rounded-xl border border-line bg-gradient-to-b from-paper-dim to-white p-6">
            <div className="flex items-center gap-4">
                {/* radar sweep to make sure all is running good */}
                <div className="relative h-14 w-14 shrink-0">
                    <div className="absolute inset-0 rounded-full border border-line" />
                    <div className="absolute inset-0 overflow-hidden rounded-full">
                        <div className="absolute inset-0 animate-[radar-spin_2.4s_linear_infinite] motion-reduce:animate-none"
                             style ={{
                                background:
                                    "conic-gradient(from 0deg, transparent 0deg, transparent 268deg, rgba(26,29,35,0.5) 312deg, transparent 360deg)",
                             }}
                        />
                    </div>
                    <div className="absolute inset-[3px] rounded-full border border-line/60 bg-white" />
                    <div className="absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-sky" />
                </div>
                <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-3">
                        <h3 className="truncate text-sm font-semibold text-ink">
                            {stage ? stage.label : "Starting up..."}
                        </h3>
                        <span className="shrink-0 font-mono text-xs tabular-nums text-charcoal">
                            {formatElapsed(elapsed)}
                        </span>
                    </div>
                    <p key={msgIdx} className="mt-1 animate-[fade-in_0.4s_ease] text-xs text-charcoal">
                        {messages[msgIdx]}
                    </p>
                </div>
            </div>
 
            <div className="mt-5 h-1.5 w-full overflow-hidden rounded-full bg-paper-dim">
                <div
                    className="h-full rounded-full bg-sky transition-[width] duration-700 ease-out"
                    style={{ width: `${progressPct}%` }}
                />
            </div>
            <div className="mt-1.5 flex justify-between text-[10px] font-semibold uppercase tracking-[0.12em] text-charcoal/70">
                <span>
                    Stage {stageNumber} of {STAGES.length}
                </span>
                <span>Usually takes a few minutes</span>
            </div>
 
            <button
                type="button"
                onClick={() => setDetailsOpen((o) => !o)}
                className="mt-4 text-xs font-semibold uppercase tracking-[0.08em] text-charcoal hover:text-ink"
            >
                {detailsOpen ? "Hide" : "Show"} details
            </button>
            {detailsOpen && (
                <pre className="mt-2 max-h-64 overflow-y-auto rounded-lg bg-ink p-3 font-mono text-xs text-paper">
                    {log.slice(-40).join("\n") || "Starting..."}
                </pre>
            )}
        </div>
    );
}