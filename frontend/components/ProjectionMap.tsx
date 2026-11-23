"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import "leaflet/dist/leaflet.css";
import type { ProjectionMap as MapData } from "@/lib/api";

// Legacy (TGG) categories. Newer results send their own `cats` and `rings` (see resolveMap).
export const CATS: Record<string, { label: string; color: string }> = {
    cava: { label: "Direct competitor (CAVA)", color: "#DC1414" },
    anchor: { label: "Grocery anchor", color: "#1E8C3C" },
    signal: { label: "Market-signal brand", color: "#285ADC" },
    new: { label: "Nick The Greek / Kebab Shop / Luna Grill", color: "#E6A014" },
};
const MI = 1609.34;

export interface ResolvedMap {
    cats: Record<string, { label: string; color: string }>;
    rings: { mi: number; color: string; label: string }[];
}

/** Category colours and rings for a map: its own if it sends them, else the TGG defaults. */
export function resolveMap(map: MapData): ResolvedMap {
    if (map.cats && map.rings) {
        return {
            cats: Object.fromEntries(map.cats.map((c) => [c.id, { label: c.label, color: c.color }])),
            rings: map.rings,
        };
    }
    return {
        cats: CATS,
        rings: [
            { mi: map.cava_radius_mi ?? 15, color: CATS.cava.color, label: `Red outline = ${map.cava_radius_mi ?? 15} mi CAVA radius used by the model` },
            { mi: map.anchor_radius_mi ?? 5, color: CATS.anchor.color, label: `green outline = ${map.anchor_radius_mi ?? 5} mi anchor radius used by the model` },
        ],
    };
}

function esc(s: string) {
    return s.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]!));
}

interface CanvasProps {
    map: MapData;
    lat: number;
    lon: number;
    siteTip: string; // tooltip text for the site marker (HTML-escaped by the caller)
    className: string;
}

function MapCanvas({ map, lat, lon, siteTip, className }: CanvasProps) {
    const el = useRef<HTMLDivElement>(null);
    const { cats, rings } = useMemo(() => resolveMap(map), [map]);

    useEffect(() => {
        let disposed = false;
        let cleanup: (() => void) | undefined;
        (async () => {
            const L = (await import("leaflet")).default;
            if (disposed || !el.current) return;
            const node = el.current;
            const m = L.map(node, { scrollWheelZoom: false, attributionControl: true });
            // OpenStreetMap's standard tiles need no API key (the Carto ones now do).
            L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
                maxZoom: 19,
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            }).addTo(m);

            const ring = (mi: number, color: string) =>
                L.circle([lat, lon], { radius: mi * MI, color, weight: 2, opacity: 0.6, fillColor: color, fillOpacity: 0.05, interactive: false }).addTo(m);
            for (const r of rings) ring(r.mi, r.color);

            // The site goes underneath, so a competitor sitting right next to it is still hoverable.
            L.circleMarker([lat, lon], { radius: 10, color: "#fff", weight: 3, fillColor: "#1B355E", fillOpacity: 1 })
                .bindTooltip(siteTip)
                .addTo(m);

            for (const p of map.points) {
                const c = cats[p.cat];
                if (!c) continue;
                const lines = [`<b>${esc(p.brand)}</b>`, esc(c.label), p.revenue && esc(p.revenue), p.rank && esc(p.rank), `${p.mi} mi away`];
                L.circleMarker([p.lat, p.lon], { radius: 6, color: "#fff", weight: 1.5, fillColor: c.color, fillOpacity: 0.9 })
                    .bindTooltip(lines.filter(Boolean).join("<br/>"))
                    .addTo(m);
            }
            const outer = Math.max(...rings.map((r) => r.mi));
            m.fitBounds(L.latLng(lat, lon).toBounds(outer * 2 * MI * 1.1));

            // Shift + scroll zooms the map; plain scrolling still scrolls the page.
            // (macOS turns Shift+scroll into sideways scrolling, so deltaX is read too.)
            let last = 0;
            const onWheel = (e: WheelEvent) => {
                if (!e.shiftKey) return;
                e.preventDefault();
                const now = Date.now();
                if (now - last < 120) return;
                last = now;
                const d = e.deltaY || e.deltaX;
                if (!d) return;
                m.setZoomAround(m.mouseEventToContainerPoint(e), m.getZoom() + (d < 0 ? 1 : -1));
            };
            node.addEventListener("wheel", onWheel, { passive: false });

            // Keep the map correct if its box changes size (window resize, the Expand window opening).
            const ro = new ResizeObserver(() => m.invalidateSize());
            ro.observe(node);

            cleanup = () => {
                ro.disconnect();
                node.removeEventListener("wheel", onWheel);
                m.remove();
            };
        })();
        return () => { disposed = true; cleanup?.(); };
    }, [map, lat, lon, siteTip]);

    return <div ref={el} className={className} role="img" aria-label="Map of competitors and anchors around the site" />;
}

/**
 * The site, the competitor / anchor locations around it and the two radius rings
 * the model uses. Hover a dot for the brand, its revenue and rank. "Expand" opens a
 * larger map in a window (not full screen). Shift + scroll zooms.
 */
export default function ProjectionMap({ map, lat, lon, siteTip }: { map: MapData; lat: number; lon: number; siteTip: string }) {
    const [big, setBig] = useState(false);

    useEffect(() => {
        if (!big) return;
        const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setBig(false); };
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [big]);

    const { cats, rings } = useMemo(() => resolveMap(map), [map]);
    const used = Object.entries(cats).filter(([k]) => map.points.some((p) => p.cat === k));
    const legend = (
        <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-charcoal">
            <li className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-ink" />This site</li>
            {used.map(([k, c]) => (
                <li key={k} className="flex items-center gap-1.5">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: c.color }} />{c.label}
                </li>
            ))}
            <li className="text-charcoal/70">(within {map.radius_mi} miles)</li>
        </ul>
    );

    return (
        <div>
            <div className="relative">
                <MapCanvas map={map} lat={lat} lon={lon} siteTip={siteTip}
                    className="h-80 w-full overflow-hidden rounded-lg border border-line bg-paper" />
                <button
                    type="button"
                    onClick={() => setBig(true)}
                    className="absolute right-3 top-3 z-[500] rounded-md border border-line bg-white px-2.5 py-1 text-xs font-semibold text-ink shadow-sm hover:bg-paper"
                >
                    Expand ⤢
                </button>
            </div>
            <div className="mt-3 space-y-1.5">
                {legend}
                <p className="text-xs text-charcoal/70">
                    {rings.map((r) => r.label).join(" · ")} · hover a dot for details · Shift + scroll to zoom
                </p>
            </div>

            {big && (
                <div
                    className="fixed inset-0 z-[1000] flex items-center justify-center bg-ink/60 p-4 sm:p-8"
                    onMouseDown={(e) => { if (e.target === e.currentTarget) setBig(false); }}
                    role="dialog"
                    aria-label="Expanded map"
                >
                    <div className="flex h-[82vh] w-full max-w-6xl flex-col rounded-xl bg-white p-4 shadow-2xl">
                        <div className="mb-3 flex items-center justify-between gap-3">
                            <div className="min-w-0">{legend}</div>
                            <button
                                type="button"
                                onClick={() => setBig(false)}
                                className="shrink-0 rounded-md border border-line px-3 py-1 text-xs font-semibold text-ink hover:bg-paper"
                            >
                                Close ✕
                            </button>
                        </div>
                        <MapCanvas map={map} lat={lat} lon={lon} siteTip={siteTip}
                            className="min-h-0 flex-1 overflow-hidden rounded-lg border border-line bg-paper" />
                        <p className="mt-2 text-xs text-charcoal/70">Shift + scroll to zoom · Esc to close</p>
                    </div>
                </div>
            )}
        </div>
    );
}