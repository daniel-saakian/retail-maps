"use client";
 
import { useState } from "react";
import { DemographicsResponse, RingProfile, api } from "@/lib/api";
 
// Keep in sync with sco/demographics_api.py's AVAILABLE_RADII -- add new
// values here (and there) as more radii become supported.
const AVAILABLE_RADII = [1, 2, 3, 5, 7, 10];
 
function fmtNum(n: number | null | undefined): string {
    if (n === null || n === undefined) return "\u2014";
    return n.toLocaleString();
}
 
function fmtPct(n: number | null | undefined): string {
    if (n === null || n === undefined) return "\u2014";
    return `${n}%`;
}
 
function fmtMoney(n: number | null | undefined): string {
    if (n === null || n === undefined) return "\u2014";
    return `$${n.toLocaleString()}`;
}
 
export default function DemographicsPage() {
    const [address, setAddress] = useState("");
    const [selectedRadii, setSelectedRadii] = useState<number[]>([1, 3]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [result, setResult] = useState<DemographicsResponse | null>(null);
 
    function toggleRadius(r: number) {
        setSelectedRadii((prev) =>
            prev.includes(r) ? prev.filter((x) => x !== r) : [...prev, r].sort((a, b) => a - b)
        );
    }
 
    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        if (!address.trim() || selectedRadii.length === 0) return;
        setLoading(true);
        setError(null);
        try {
            const data = await api.getDemographics(address.trim(), selectedRadii);
            setResult(data);
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setLoading(false);
        }
    }
 
    return (
        <main className="mx-auto max-w-6xl px-6 py-10">
            <header className="mb-8">
                <h1 className="font-display text-3xl font-bold text-ink">Demographics</h1>
                <div className="wedge-divider mt-3 mb-2 max-w-xs">
                    <span className="whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.18em] text-charcoal">
                        Trade Area Profile
                    </span>
                </div>
                <p className="text-sm text-charcoal">
                    Pull census demographics, spending, and employment data around a specific address.
                </p>
            </header>
 
            <form onSubmit={handleSubmit} className="rounded-xl border border-line bg-white p-5 shadow-sm">
                <label className="text-sm">
                    <span className="mb-1 block font-medium text-charcoal">Address</span>
                    <input
                        value={address}
                        onChange={(e) => setAddress(e.target.value)}
                        placeholder='e.g. "1151 Galleria Blvd, Roseville, CA"'
                        className="w-full rounded-lg border border-line bg-paper px-4 py-2.5 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                    />
                </label>
 
                <div className="mt-4">
                    <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.1em] text-charcoal">
                        Radii to pull
                    </span>
                    <div className="flex flex-wrap gap-2">
                        {AVAILABLE_RADII.map((r) => {
                            const active = selectedRadii.includes(r);
                            return (
                                <button
                                    key={r}
                                    type="button"
                                    onClick={() => toggleRadius(r)}
                                    className={`rounded-full border px-4 py-1.5 text-sm font-semibold transition ${
                                        active
                                            ? "border-success bg-success text-white"
                                            : "border-line bg-white text-charcoal hover:border-sky hover:text-ink"
                                    }`}
                                >
                                    {r} mi
                                </button>
                            );
                        })}
                    </div>
                </div>
 
                <button
                    type="submit"
                    disabled={loading || !address.trim() || selectedRadii.length === 0}
                    className="mt-5 rounded-lg bg-ink px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-2 disabled:opacity-40"
                >
                    {loading ? "Pulling demographics..." : "Run"}
                </button>
                {loading && (
                    <p className="mt-2 text-xs text-charcoal/70">
                        This queries the Census Bureau and employment data directly -- can take up to a minute.
                    </p>
                )}
                {error && (
                    <p className="mt-3 rounded-lg bg-danger/10 p-3 text-sm text-danger-dark">{error}</p>
                )}
            </form>
 
            {result && <ResultsView result={result} />}
        </main>
    );
}
 
function ResultsView({ result }: { result: DemographicsResponse }) {
    const ringEntries = Object.entries(result.rings).sort(
        ([a], [b]) => parseFloat(a) - parseFloat(b)
    );
 
    return (
        <div className="mt-10 flex flex-col gap-20">
            <div className="rounded-xl border border-line bg-white p-6 shadow-sm">
                <p className="font-display text-xl font-bold text-ink">{result.address}</p>
                <p className="mt-1 text-xs text-charcoal/70">
                    {result.lat.toFixed(5)}, {result.lon.toFixed(5)}
                </p>
                <div className="mt-5 flex gap-10 border-t border-line pt-5">
                    <Stat label="Renter Occupied" value={fmtPct(result.renter_pct)} prominent />
                    <Stat label="Work From Home" value={fmtPct(result.wfh_pct)} prominent />
                </div>
            </div>
 
            <TopicSection title="Population">
                {ringEntries.map(([key, ring]) => (
                    <RadiusColumn key={key} label={`${key} mi`}>
                        <Stat label="Population" value={fmtNum(ring.population)} prominent />
                        <Stat label="Daytime Population" value={fmtNum(ring.daytime_population)} prominent />
                    </RadiusColumn>
                ))}
            </TopicSection>
 
            <TopicSection title="Age & Race">
                {ringEntries.map(([key, ring]) => {
                    const known =
                        (ring.white_pct || 0) + (ring.black_pct || 0) + (ring.hispanic_pct || 0) + (ring.asian_pct || 0);
                    const other = Math.max(0, 100 - known);
                    return (
                        <RadiusColumn key={key} label={`${key} mi`}>
                            <Stat label="Median Age" value={ring.median_age ? String(ring.median_age) : "\u2014"} />
                            <MiniPie
                                segments={[
                                    { label: "White", value: ring.white_pct || 0, color: "#1B355E" },
                                    { label: "Hispanic", value: ring.hispanic_pct || 0, color: "#B8934A" },
                                    { label: "Black", value: ring.black_pct || 0, color: "#2AA7DE" },
                                    { label: "Asian", value: ring.asian_pct || 0, color: "#3F7D58" },
                                    { label: "Other", value: other, color: "#B9B2A0" },
                                ]}
                            />
                        </RadiusColumn>
                    );
                })}
            </TopicSection>
 
            <TopicSection title="Employment">
                {ringEntries.map(([key, ring]) => (
                    <RadiusColumn key={key} label={`${key} mi`}>
                        <Stat label="Employees" value={fmtNum(ring.employee_count)} prominent />
                        <MiniPie
                            segments={[
                                { label: "White Collar", value: ring.white_collar_pct || 0, color: "#1B355E" },
                                { label: "Blue Collar", value: ring.blue_collar_pct || 0, color: "#2AA7DE" },
                            ]}
                        />
                    </RadiusColumn>
                ))}
            </TopicSection>
 
            <TopicSection title="Income & Spending">
                {ringEntries.map(([key, ring]) => (
                    <RadiusColumn key={key} label={`${key} mi`}>
                        <Stat label="Median HH Income" value={fmtMoney(ring.median_hh_income)} prominent />
                        <Stat label="Annual Dining Spend" value={fmtMoney(ring.hh_dining_spend)} />
                        <Stat label="Annual Discretionary Spend" value={fmtMoney(ring.hh_discretionary_spend)} />
                    </RadiusColumn>
                ))}
            </TopicSection>
        </div>
    );
}
 
function TopicSection({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <section>
            <div className="wedge-divider mb-5">
                <span className="whitespace-nowrap font-display text-lg font-bold text-ink">{title}</span>
            </div>
            <div className="flex flex-nowrap justify-center gap-x-12 overflow-x-auto">{children}</div>
        </section>
    );
}
 
function RadiusColumn({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <div className="w-32 shrink-0 text-center">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.12em] text-sky">{label}</p>
            <div className="flex flex-col items-center gap-5">{children}</div>
        </div>
    );
}
 
function MiniPie({
    segments,
    size = 140,
}: {
    segments: { label: string; value: number; color: string }[];
    size?: number;
}) {
    const total = segments.reduce((s, x) => s + x.value, 0) || 1;
    let cumulative = 0;
    const stops = segments
        .map((s) => {
            const start = (cumulative / total) * 360;
            cumulative += s.value;
            const end = (cumulative / total) * 360;
            return `${s.color} ${start}deg ${end}deg`;
        })
        .join(", ");
 
    return (
        <div className="flex flex-col items-center gap-2">
            <div
                className="rounded-full"
                style={{ width: size, height: size, background: `conic-gradient(${stops})` }}
            />
            <div className="flex w-full flex-col gap-0.5">
                {segments
                    .filter((s) => s.value > 0)
                    .map((s) => (
                        <div key={s.label} className="flex items-center justify-between gap-2 text-[11px] text-charcoal">
                            <span className="flex items-center gap-1">
                                <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: s.color }} />
                                {s.label}
                            </span>
                            <span className="font-medium text-ink">{((s.value / total) * 100).toFixed(0)}%</span>
                        </div>
                    ))}
            </div>
        </div>
    );
}
 
function Stat({
    label,
    value,
    prominent = false,
}: {
    label: string;
    value: string;
    prominent?: boolean;
}) {
    return (
        <div className="text-center">
            <p className="text-xs text-charcoal">{label}</p>
            <p className={`text-ink ${prominent ? "text-2xl font-semibold" : "text-base font-medium"}`}>
                {value}
            </p>
        </div>
    );
}