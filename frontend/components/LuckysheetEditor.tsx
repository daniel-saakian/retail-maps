"use client";

import {
    forwardRef,
    useEffect,
    useImperativeHandle,
    useRef,
    useState,
} from "react";
 
const CDN_BASE = "https://cdn.jsdelivr.net/npm/luckysheet@2.1.13/dist";
 
declare global {
    interface Window {
        luckysheet?: {
            create: (options: Record<string, unknown>) => void;
            destroy: () => void;
            getAllSheets: () => unknown[];
        };
        LuckyExcel?: {
            transformExcelToLucky: (
                file: File,
                success: (exportJson: { sheets: unknown[] }, luckysheetfile: unknown) => void,
                error: (err: unknown) => void
            ) => void;
        };
    }
}
 
let loadPromise: Promise<void> | null = null;
 
function loadLuckysheetOnce(): Promise<void> {
    if (loadPromise) return loadPromise;
 
    loadPromise = new Promise((resolve, reject) => {
        const css = [
            `${CDN_BASE}/plugins/css/pluginsCss.css`,
            `${CDN_BASE}/plugins/plugins.css`,
            `${CDN_BASE}/css/luckysheet.css`,
            `${CDN_BASE}/assets/iconfont/iconfont.css`,
        ];
        for (const href of css) {
            if (document.querySelector(`link[href="${href}"]`)) continue;
            const link = document.createElement("link");
            link.rel = "stylesheet";
            link.href = href;
            document.head.appendChild(link);
        }
 
        function loadScript(src: string): Promise<void> {
            return new Promise((res, rej) => {
                const existing = document.querySelector(`script[src="${src}"]`);
                if (existing) {
                    res();
                    return;
                }
                const script = document.createElement("script");
                script.src = src;
                script.async = true;
                script.onload = () => res();
                script.onerror = () => rej(new Error(`Failed to load ${src}`));
                document.body.appendChild(script);
            });
        }
 
        // plugin.js bundles Luckysheet's own jQuery/plugin dependencies --
        // must load before luckysheet.umd.js, and luckyexcel needs plugin.js
        // loaded first too since it shares some of the same globals.
        loadScript(`${CDN_BASE}/plugins/js/plugin.js`)
            .then(() => loadScript(`${CDN_BASE}/luckysheet.umd.js`))
            .then(() => loadScript("https://cdn.jsdelivr.net/npm/luckyexcel@1.0.1/dist/luckyexcel.umd.js"))
            .then(() => resolve())
            .catch(reject);
    });
 
    return loadPromise;
}
 
export interface LuckysheetEditorHandle {
    getEditedSheets: () => unknown[];
}
 
interface LuckysheetEditorProps {
    file: Blob;
    onReady?: () => void;
    onError?: (message: string) => void;
    height?: number | string;
}
 
const LuckysheetEditor = forwardRef<LuckysheetEditorHandle, LuckysheetEditorProps>(
    function LuckysheetEditor({ file, onReady, onError, height = 640 }, ref) {
        const containerRef = useRef<HTMLDivElement>(null);
        const containerId = useRef(`luckysheet-${Math.random().toString(36).slice(2)}`);
        const [loadingLabel, setLoadingLabel] = useState<string | null>("Loading editor...");
 
        useImperativeHandle(ref, () => ({
            getEditedSheets: () => window.luckysheet?.getAllSheets() ?? [],
        }));
 
        useEffect(() => {
            let cancelled = false;
 
            setLoadingLabel("Loading editor...");
            loadLuckysheetOnce()
                .then(() => {
                    if (cancelled) return;
                    setLoadingLabel("Reading workbook...");
                    const excelFile = new File([file], "preview.xlsx", {
                        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    });
                    window.LuckyExcel?.transformExcelToLucky(
                        excelFile,
                        (exportJson) => {
                            if (cancelled) return;
                            if (!exportJson || !exportJson.sheets || exportJson.sheets.length === 0) {
                                onError?.("Couldn't read the generated workbook.");
                                return;
                            }
                            window.luckysheet?.destroy();
                            window.luckysheet?.create({
                                container: containerId.current,
                                title: "Site Presentation",
                                lang: "en",
                                showtoolbar: true,
                                showinfobar: false,
                                data: exportJson.sheets,
                            });
                            if (!cancelled) {
                                setLoadingLabel(null);
                                onReady?.();
                            }
                        },
                        (err) => {
                            if (!cancelled) onError?.(String(err));
                        }
                    );
                })
                .catch((err) => {
                    if (!cancelled) onError?.(String(err));
                });
 
            return () => {
                cancelled = true;
                window.luckysheet?.destroy();
            };
        }, [file]);
 
        return (
            <div className="relative" style={{ height }}>
                <div
                    id={containerId.current}
                    ref={containerRef}
                    className="absolute inset-0 overflow-hidden rounded-xl border border-line"
                />
                {loadingLabel && (
                    <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-white text-sm text-charcoal/70">
                        {loadingLabel}
                    </div>
                )}
            </div>
        );
    }
);
 
export default LuckysheetEditor;