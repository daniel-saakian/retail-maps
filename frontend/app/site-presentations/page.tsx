"use client";
 
import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { SitePresentationBrand, api } from "@/lib/api";
import type { LuckysheetEditorHandle } from "@/components/LuckysheetEditor";


const LuckysheetEditor = dynamic(() => import("@/components/LuckysheetEditor"), {
    ssr: false,
});
 
export default function SitePresentationsPage() {
    const [brands, setBrands] = useState<SitePresentationBrand[]>([]);
    const [brandsError, setBrandsError] = useState<string | null>(null);
    const [brand, setBrand] = useState("");
    const [address, setAddress] = useState("");
 
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
 
    useEffect(() => {
        if (!isFullscreen) return;
        const prevOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        return () => {
            document.body.style.overflow = prevOverflow;
        };
    }, [isFullscreen]);
 
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
        const controller = new AbortController();
        abortRef.current = controller;
        setGenerating(true);
        setCancelled(false);
        setError(null);
        setDownloaded(false);
        setEditorReady(false);
        setPreviewFile(null);
        try {
            const { blob, filename } = await api.previewSitePresentation(brand, address.trim(), controller.signal);
            setPreviewFile(blob);
            setPreviewFilename(filename);
        } catch (e) {
            if ((e as Error).name === "AbortError") {
                setCancelled(true);
            } else {
                setError((e as Error).message);
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
                            className="rounded-lg border border-line px-4 py-2.5 text-sm font-semibold text-charcoal transition hover:bg-paper"
                        >
                            Cancel
                        </button>
                    )}
                </div>
 
                {generating && (
                    <div className="mt-4">
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-paper">
                            <div className="loading-bar-fill h-full w-1/3 rounded-full bg-sky" />
                        </div>
                        <p className="mt-2 text-xs text-charcoal/70">
                            Pulling demographics, competitors, and traffic data, then building
                            the site summary -- can take a moment.
                        </p>
                        <style jsx>{`
                            .loading-bar-fill {
                                animation: loading-bar-slide 1.2s ease-in-out infinite;
                            }
                            @keyframes loading-bar-slide {
                                0% {
                                    transform: translateX(-100%);
                                }
                                100% {
                                    transform: translateX(300%);
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