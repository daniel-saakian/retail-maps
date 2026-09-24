"use client";
 
import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { SitePresentationBrand, api } from "@/lib/api";
import type { LuckysheetEditorHandle } from "@/components/LuckysheetEditor";
 
const LuckysheetEditor = dynamic(() => import("@/components/LuckysheetEditor"), {
    ssr: false,
});
 
const GENERATE_STAGES = [
    "Geocoding address...",
    "Pulling demographics...",
    "Scanning competitors...",
    "Mapping co-tenants...",
    "Checking traffic counts...",
    "Building the site summary...",
];
 
export default function SitePresentationsPage() {
    const [brands, setBrands] = useState<SitePresentationBrand[]>([]);
    const [brandsError, setBrandsError] = useState<string | null>(null);
    const [brand, setBrand] = useState("");
    const [address, setAddress] = useState("");






    const [showAdvanced, setShowAdvanced] = useState(false);
    const [manualLat, setManualLat] = useState("");
    const [manualLon, setManualLon] = useState("");
 
    const [generating, setGenerating] = useState(false);
    const [error, setError] = useState<string | null>(null);
 
    const [previewFile, setPreviewFile] = useState<Blob | null>(null);
    const [previewFilename, setPreviewFilename] = useState<string>("site_summary.xlsx");
    const [editorReady, setEditorReady] = useState(false);
 
    const [downloading, setDownloading] = useState(false);
    const [downloaded, setDownloaded] = useState(false);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [cancelled, setCancelled] = useState(false);
 
    const editorRef = useRef<LuckysheetEditorHandle>(null);
    const abortRef = useRef<AbortController | null>(null);
 
    const [stageIndex, setStageIndex] = useState(0);
    const [progress, setProgress] = useState(0);
 
    useEffect(() => {
        if (!generating) {
            setProgress(0);
            setStageIndex(0);
            return;
        }
        const stageTimer = setInterval(() => {
            setStageIndex((i) => Math.min(i + 1, GENERATE_STAGES.length - 1));
        }, 3200);
        const progressTimer = setInterval(() => {

            setProgress((p) => (p >= 92 ? p : p + (92 - p) * 0.06));
        }, 200);
        return () => {
            clearInterval(stageTimer);
            clearInterval(progressTimer);
        };
    }, [generating]);
 
    // Lock page scroll only while the editor is actually fullscreen -- in
    // the embedded layout the page scrolls normally.
    useEffect(() => {
        if (!isFullscreen) return;
        const prevOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        return () => {
            document.body.style.overflow = prevOverflow;
        };
    }, [isFullscreen]);
 
    // Esc exits fullscreen, same as any other fullscreen surface on the web.
    useEffect(() => {
        if (!isFullscreen) return;
        function onKey(e: KeyboardEvent) {
            if (e.key === "Escape") setIsFullscreen(false);
        }
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [isFullscreen]);
 
    useEffect(() => {
        api
            .listSitePresentationBrands()
            .then((list) => {
                setBrands(list);
                if (list.length > 0) setBrand((prev) => prev || list[0].code);
            })
            .catch((e) => setBrandsError((e as Error).message));
    }, []);
 
    async function handleGenerate(e: React.FormEvent) {
        e.preventDefault();
        if (!brand || !address.trim()) return;

        const trimmedLat = manualLat.trim();
        const trimmedLon = manualLon.trim();
        let coords: { lat: number, lon: number } | undefined;
        if (trimmedLat || trimmedLon) {
            const lat = Number(trimmedLat);
            const lon = Number(trimmedLon);
            if (trimmedLat === "" || trimmedLon === "" || Number.isNaN(lat) || Number.isNaN(lon)) {
                setError("Enter both latitude and longitude in Advanced Settings, or leave both empty");
                return;
            }
            coords = {lat, lon};
        }

        const controller = new AbortController();
        abortRef.current = controller;
        setGenerating(true);
        setCancelled(false);
        setError(null);
        setDownloaded(false);
        setEditorReady(false);
        setPreviewFile(null);
        try {
            const { blob, filename } = await api.previewSitePresentation(
                brand,
                address.trim(),
                controller.signal,
                coords
            );
            setProgress(100);
            await new Promise((resolve) => setTimeout(resolve, 220));
            setPreviewFile(blob);
            setPreviewFilename(filename);
        } catch (e) {
            if ((e as Error).name === "AbortError") {
                setCancelled(true);
            } else {
                const message = (e as Error).message;
                setError(message);
                // The backend sends this exact wording when geocoding fails
                // and no fallback coordinates were provided -- reveal
                // Advanced Settings automatically so the person doesn't
                // have to go hunting for where to enter them.
                if (message.includes("Advanced Settings")) {
                    setShowAdvanced(true);
                }
            }
        } finally {
            setGenerating(false);
            abortRef.current = null;
        }
    }
 
    function handleCancel() {
        abortRef.current?.abort();
    }
 
    async function handleDownload() {
        if (!editorRef.current) return;
        setDownloading(true);
        setError(null);
        try {
            const sheets = editorRef.current.getEditedSheets();
            await api.exportSitePresentation(previewFilename, sheets);
            setDownloaded(true);
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setDownloading(false);
        }
    }
 
    return (
        <main className="mx-auto max-w-6xl px-6 py-10">
            <header className="mb-8">
                <h1 className="font-display text-3xl font-bold text-ink">Site Presentations</h1>
                <div className="wedge-divider mt-3 mb-2 max-w-xs">
                    <span className="whitespace-nowrap text-[11px] font-semibold uppercase tracking-[0.18em] text-charcoal">
                        Client Templates
                    </span>
                </div>
                <p className="text-sm text-charcoal">
                    Pick a client, drop in an address, review and tweak the site summary, then
                    download it.
                </p>
            </header>
 
            <form onSubmit={handleGenerate} className="rounded-xl border border-line bg-white p-5 shadow-sm">
                <div className="grid gap-4 sm:grid-cols-[220px_1fr]">
                    <label className="text-sm">
                        <span className="mb-1 block font-medium text-charcoal">Client</span>
                        <select
                            value={brand}
                            onChange={(e) => setBrand(e.target.value)}
                            disabled={brands.length === 0}
                            className="w-full rounded-lg border border-line bg-paper px-3 py-2.5 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky disabled:opacity-50"
                        >
                            {brands.length === 0 && <option value="">No clients available</option>}
                            {brands.map((b) => (
                                <option key={b.code} value={b.code}>
                                    {b.label}
                                </option>
                            ))}
                        </select>
                    </label>
 
                    <label className="text-sm">
                        <span className="mb-1 block font-medium text-charcoal">Address</span>
                        <input
                            value={address}
                            onChange={(e) => setAddress(e.target.value)}
                            placeholder='e.g. "1151 Galleria Blvd, Roseville, CA"'
                            className="w-full rounded-lg border border-line bg-paper px-4 py-2.5 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                        />
                    </label>
                </div>
 
                <div className="mt-3">
                    <button
                        type="button"
                        onClick={() => setShowAdvanced((v) => !v)}
                        className="text-xs font-semibold text-charcoal/70 underline decoration-dotted underline-offset-2 hover:text-charcoal"
                    >
                        {showAdvanced ? "Hide" : "Show"} Advanced Settings
                    </button>
                    {showAdvanced && (
                        <div className="mt-2 grid gap-3 rounded-lg border border-line bg-paper p-3 sm:grid-cols-2">
                            <label className="text-sm">
                                <span className="mb-1 block font-medium text-charcoal">
                                    Latitude <span className="font-normal text-charcoal/60">(optional)</span>
                                </span>
                                <input
                                    value={manualLat}
                                    onChange={(e) => setManualLat(e.target.value)}
                                    inputMode="decimal"
                                    placeholder="e.g. 32.680396"
                                    className="w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                                />
                            </label>
                            <label className="text-sm">
                                <span className="mb-1 block font-medium text-charcoal">
                                    Longitude <span className="font-normal text-charcoal/60">(optional)</span>
                                </span>
                                <input
                                    value={manualLon}
                                    onChange={(e) => setManualLon(e.target.value)}
                                    inputMode="decimal"
                                    placeholder="e.g. -97.105358"
                                    className="w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink outline-none focus:border-sky focus:ring-1 focus:ring-sky"
                                />
                            </label>
                            <p className="text-xs text-charcoal/60 sm:col-span-2">
                                Only used as a fallback if the address above can&apos;t be geocoded.
                                Keep the address filled in either way -- it&apos;s still what shows
                                at the top of the report.
                            </p>
                        </div>
                    )}
                </div>
 
                <div className="mt-5 flex items-center gap-3">
                    <button
                        type="submit"
                        disabled={generating || !brand || !address.trim()}
                        className="rounded-lg bg-ink px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-2 disabled:opacity-40"
                    >
                        {generating ? "Generating..." : "Generate"}
                    </button>
                    {generating && (
                        <button
                            type="button"
                            onClick={handleCancel}
                            className="group flex items-center gap-1.5 rounded-lg border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm font-semibold text-danger-dark transition hover:border-danger/50 hover:bg-danger/10"
                        >
                            <span className="block h-2 w-2 rounded-[2px] bg-danger-dark transition group-hover:scale-90" />
                            Cancel
                        </button>
                    )}
                </div>
 
                {generating && (
                    <div className="mt-4">
                        <div className="mb-1.5 flex items-center justify-between">
                            <p className="text-xs font-medium text-charcoal">
                                {GENERATE_STAGES[stageIndex]}
                            </p>
                            <p className="font-display text-xs font-semibold tabular-nums text-charcoal/60">
                                {Math.round(progress)}%
                            </p>
                        </div>
                        <div className="relative h-2 w-full overflow-hidden rounded-full bg-paper">
                            <div
                                className="site-progress-fill h-full rounded-full bg-gradient-to-r from-sky to-ink transition-[width] duration-300 ease-out"
                                style={{ width: `${progress}%` }}
                            />
                            <div className="site-progress-shimmer pointer-events-none absolute inset-y-0 left-0 w-1/4 rounded-full" />
                        </div>
                        <p className="mt-2 text-xs text-charcoal/70">
                            Can take a moment -- pulling live data from several sources.
                        </p>
                        <style jsx>{`
                            .site-progress-shimmer {
                                background: linear-gradient(
                                    90deg,
                                    transparent,
                                    rgba(255, 255, 255, 0.55),
                                    transparent
                                );
                                animation: site-progress-shimmer-slide 1.6s ease-in-out infinite;
                            }
                            @keyframes site-progress-shimmer-slide {
                                0% {
                                    transform: translateX(-100%);
                                }
                                100% {
                                    transform: translateX(400%);
                                }
                            }
                        `}</style>
                    </div>
                )}
                {cancelled && !generating && (
                    <p className="mt-3 rounded-lg bg-paper p-3 text-sm text-charcoal">
                        Generation cancelled.
                    </p>
                )}
                {brandsError && (
                    <p className="mt-3 rounded-lg bg-danger/10 p-3 text-sm text-danger-dark">
                        Couldn&apos;t load clients: {brandsError}
                    </p>
                )}
                {error && (
                    <p className="mt-3 rounded-lg bg-danger/10 p-3 text-sm text-danger-dark">{error}</p>
                )}
            </form>
 
            {previewFile && (
                <section
                    className={
                        isFullscreen
                            ? "fixed inset-0 z-50 flex flex-col bg-white"
                            : "mt-8"
                    }
                >
                    <div
                        className={
                            isFullscreen
                                ? "flex items-center justify-between gap-4 border-b border-line px-6 py-3"
                                : "mb-3 flex items-center justify-between"
                        }
                    >
                        <div>
                            <h2 className="font-display text-lg font-bold text-ink">Preview</h2>
                            <p className="text-xs text-charcoal/70">
                                Edit any cell directly below, then download when it looks right.
                            </p>
                        </div>
                        <div className="flex items-center gap-3">
                            {downloaded && isFullscreen && (
                                <span className="rounded-lg bg-success/10 px-3 py-1.5 text-sm text-success-dark">
                                    Downloaded.
                                </span>
                            )}
                            {error && isFullscreen && (
                                <span className="rounded-lg bg-danger/10 px-3 py-1.5 text-sm text-danger-dark">
                                    {error}
                                </span>
                            )}
                            <button
                                onClick={() => setIsFullscreen((v) => !v)}
                                className="rounded-lg border border-line px-4 py-2.5 text-sm font-semibold text-charcoal transition hover:bg-paper"
                                title={isFullscreen ? "Exit fullscreen (Esc)" : "Expand to fullscreen"}
                            >
                                {isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
                            </button>
                            <button
                                onClick={handleDownload}
                                disabled={!editorReady || downloading}
                                className="rounded-lg bg-ink px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-2 disabled:opacity-40"
                            >
                                {downloading ? "Downloading..." : "Download"}
                            </button>
                        </div>
                    </div>
 
                    {!isFullscreen && downloaded && (
                        <p className="mb-3 rounded-lg bg-success/10 p-3 text-sm text-success-dark">
                            Downloaded.
                        </p>
                    )}
                    {!isFullscreen && error && (
                        <p className="mb-3 rounded-lg bg-danger/10 p-3 text-sm text-danger-dark">{error}</p>
                    )}
 
                    <div className={isFullscreen ? "min-h-0 flex-1" : ""}>
                        <LuckysheetEditor
                            ref={editorRef}
                            file={previewFile}
                            onReady={() => setEditorReady(true)}
                            onError={(msg) => setError(msg)}
                            height={isFullscreen ? "100%" : 640}
                        />
                    </div>
                </section>
            )}
        </main>
    );
}