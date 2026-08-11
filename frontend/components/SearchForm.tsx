"use client";

import { useEffect, useState } from "react";

const KM_PER_MILE = 1.60934;
function kmToMi(km: number): number {
    return Math.round((km / KM_PER_MILE) * 10) / 10;
}
function miToKm(mi: number): number {
    return mi * KM_PER_MILE;
}

export default function SearchForm({
    defaultSearchKm,
    onSubmit,
}: {
    defaultSearchKm: number,
    onSubmit: (city:string, searchKm: number, rescrapeDays: number | null) => Promise<void>;
}) {
    const [city, setCity] = useState("");
    const [searchMi, setSearchMi] = useState(kmToMi(defaultSearchKm));
    const [radiusTouched, setRadiusTouched] = useState(false)
    const [advancedOpen, setAdvancedOpen] = useState(false);
    const [rescrapeEnabled, setRescrapeEnabled] = useState(false);
    const [rescrapeDays, setRescrapeDays] = useState(30);
    const [submitting, setSubmitting] = useState(false);

    useEffect(() => {
        if (!radiusTouched) setSearchMi(kmToMi(defaultSearchKm));
    }, [defaultSearchKm, radiusTouched]);

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (!city.trim() || submitting) return;
        setSubmitting(true);
        try {
            await onSubmit(city.trim(), miToKm(searchMi), rescrapeEnabled ? rescrapeDays : null);
            setCity("");
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <form onSubmit={handleSubmit} className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex gap-3">
                <input
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    placeholder='City to search, e.g. "Roseville, CA"'
                    className="flex-1 rounded-lg border border-line bg-paper px-4 py-2.5 text-sm text-ink outline-none placeholder:text-charcoal/50 focus:border-sky focus:rink-1 focus:ring-sky"
                />
                <button
                    type="submit"
                    disabled={submitting || !city.trim()}
                    className="rounded-lg bg-ink px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-2 disabled:opacity-40"
                >
                    {submitting ? "Starting..." : "Run search"}
                </button>
            </div>

            <button
                type="button"
                onClick={() => setAdvancedOpen((o) => !o)}
                className="mt-3 text-xs font-semibold uppercase tracking-[0.1em] text-charcoal hover:text-ink"
            >
                {advancedOpen ? "Hide" : "Show"} advanced options
            </button>

            {advancedOpen && (
                <div className="mt-3 flex flex-wrap items-center gap-6 border-t border-line pt-3 text-sm text-ink">
                    <label className="flex items-center gap-2">
                        Search radius (miles)
                        <input
                            type="number"
                            value={searchMi}
                            min={1}
                            max={80}
                            step={0.5}
                            onChange={(e) => {
                                setRadiusTouched(true);
                                setSearchMi(Number(e.target.value));
                            }}
                            className="w-20 rounded border border-line bg-paper px-2 py-1 font-mono focus:border-sky focus:outline-none"
                        />
                    </label>
                    <label className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            checked={rescrapeEnabled}
                            onChange={(e) => setRescrapeEnabled(e.target.checked)}
                            className="accent-sky"
                        />
                        Re-scrape if brokers older than
                        <input
                            type="number"
                            value={rescrapeDays}
                            min={1}
                            disabled={!rescrapeEnabled}
                            onChange={(e) => setRescrapeDays(Number(e.target.value))}
                            className="w-16 rounded border border-line bg-paper px-2 py-1 font-mono focus:border-sky focus:outline-none disabled:opacity-40"
                        />
                        days
                    </label>
                </div>
            )}
        </form>
    );
}