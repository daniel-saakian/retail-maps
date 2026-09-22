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
 
    const editorRef = useRef<LuckysheetEditorHandle>(null);
 
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
        setGenerating(true);
        setError(null);
        setDownloaded(false);
        setEditorReady(false);
        setPreviewFile(null);
        try {
            const { blob, filename } = await api.previewSitePresentation(brand, address.trim());
            setPreviewFile(blob);
            setPreviewFilename(filename);
        } catch (e) {
            setError((e as Error).message);
        } finally {
            setGenerating(false);
        }
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
 
                <button
                    type="submit"
                    disabled={generating || !brand || !address.trim()}
                    className="mt-5 rounded-lg bg-ink px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-2 disabled:opacity-40"
                >
                    {generating ? "Generating..." : "Generate"}
                </button>
                {generating && (
                    <p className="mt-2 text-xs text-charcoal/70">
                        Pulling demographics, competitors, and traffic data, then building the
                        site summary -- can take a moment.
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
                <section className="mt-8">
                    <div className="mb-3 flex items-center justify-between">
                        <div>
                            <h2 className="font-display text-lg font-bold text-ink">Preview</h2>
                            <p className="text-xs text-charcoal/70">
                                Edit any cell directly below, then download when it looks right.
                            </p>
                        </div>
                        <button
                            onClick={handleDownload}
                            disabled={!editorReady || downloading}
                            className="rounded-lg bg-ink px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-2 disabled:opacity-40"
                        >
                            {downloading ? "Downloading..." : "Download"}
                        </button>
                    </div>
 
                    {downloaded && (
                        <p className="mb-3 rounded-lg bg-success/10 p-3 text-sm text-success-dark">
                            Downloaded.
                        </p>
                    )}
 
                    <LuckysheetEditor
                        ref={editorRef}
                        file={previewFile}
                        onReady={() => setEditorReady(true)}
                        onError={(msg) => setError(msg)}
                        height={640}
                    />
                </section>
            )}
        </main>
    );
}