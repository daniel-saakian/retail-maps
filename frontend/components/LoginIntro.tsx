"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { logo_aspect, tile, tileInset } from "@/lib/logoTile";

const speed = 1.4;
const ms = (n:number) => n * speed;

const useIsoLayoutEffect = typeof window === "undefined" ? useEffect: useLayoutEffect;

type Pt = {x: number, y: number};

export default function LoginIntro() {
    const params = useSearchParams();
    const wanted = params.get("welcome") === "1";

    const [playing, setPlaying] = useState(wanted);
    const started = useRef(false);
    const skipRef = useRef<() => void>(() => {});
    const wrapRef = useRef<HTMLDivElement>(null);
    const bgRef = useRef<HTMLDivElement>(null);

    useIsoLayoutEffect(() => {
        if (!wanted) {
            started.current = false;
            return;
        }
        if (started.current) return;
        started.current = true;
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        setPlaying(!reduce);
    }, [wanted]);

    useIsoLayoutEffect(() => {
        if (!playing) return;
        const wrap = wrapRef.current;
        const bg = bgRef.current;
        if (!wrap || !bg) return;

        const vw = window.innerWidth;
        const vh = window.innerHeight;

        const W = Math.min(300, vw - 48);
        const H = W / logo_aspect;
        wrap.style.width = `${W}px`;
        wrap.style.height = `${H}px`;

        const cx = W * (tile.left + tile.w / 2);
        const cy = H * (tile.top + tile.h / 2);
        const tilePx = W * tile.w;

        const at = (p: Pt, s: number) => `translate(${p.x}px, ${p.y}px) scale(${s})`;

        const start: Pt = { x: (vw - W) / 2, y: Math.max(24, (vh - 570) / 2) };
        const center: Pt = { x: (vw - W) / 2, y: (vh - H) / 2 };
        
        const sA = (Math.min(vw, vh) * 0.72) / tilePx;
        const zoom: Pt= { x: vw / 2 - sA * cx, y: vh / 2 - sA * cy};

        const mark = document.querySelector<HTMLElement>("[data-nav-mark]");
        const r = mark?.getBoundingClientRect();
        const size = r?.width || 28;
        const targetCx = r ? r.left + r.width / 2 : Math.max(24, (vw - 1152) / 2 + 24) + size / 2;
        const targetCy = r ? r.top + r.height / 2 : 28;
        const sB = size / tilePx;
        const dock: Pt = {x: targetCx - sB * cx, y: targetCy - sB * cy};

        if (mark) mark.style.visibility = "hidden";

        wrap.style.opacity = "1";
        wrap.style.transform = at(start, 1);

        const tSettle = ms(350);
        const tHold = ms(100);
        const tZoom = ms(1000);
        const tGap = ms(150);
        const tDock = ms(900);
        const tZoomAt = tSettle + tHold;
        const tDockAt = tZoomAt + tZoom + tGap;

        const anims: Animation[] = [];
        const add = (el: HTMLElement, kf: Keyframe[], o: KeyframeAnimationOptions) => {
            const a = el.animate(kf, {fill: "forwards", ...o });
            anims.push(a);
            return a;
        };

        add(wrap, [{ transform: at(start, 1) }, { transform: at(center, 1) }],
            { duration: tSettle, easing: "cubic-bezier(0.3,0.7,0.3,1)" });
        add(wrap, [{ transform: at(center, 1) }, { transform: at(zoom, sA) }],
            { duration: tZoom, delay: tZoomAt, easing: "cubic-bezier(0.65,0,0.25,1)" });

        add(wrap, [{ clipPath: "inset(0%)" }, { clipPath: tileInset() }],
            { duration: ms(450), delay: tZoomAt + ms(550), easing: "ease-in-out" });
        const landed = add(wrap, [{ transform: at(zoom, sA)}, {transform:at(dock,sB)}],
            {duration: tDock, delay: tDockAt, easing: "cubic-bezier(0.7,1,0.2,1)"});
        add(bg, [{ opacity: 1 }, { opacity: 0 }],
            {duration: ms(650), delay: tDockAt + ms(150), easing: "ease-out"});

        let done = false;
        const finish = () => {
            if (done) return;
            done = true;
            if (mark) mark.style.visibility = "";
            setPlaying(false);
        };
        skipRef.current = finish;
        landed.finished.then(finish).catch(() => {});

        const onKey = (e: KeyboardEvent) => {if (e.key === "Escape") finish(); };
        window.addEventListener("keydown", onKey);

        return () => {
            window.removeEventListener("keydown", onKey);
            anims.forEach((a) => a.cancel());
            if (mark) mark.style.visibility = "";
        };
    }, [playing]);

    if (!playing) return null;

    return (
        <div
            aria-hidden
            onClick={() => skipRef.current()}
            className="fixed inset-0 z-[60] cursor pointer overflow-hidden"
        >
            <div ref={bgRef} className="absolute inset-0 bg-paper" />
            <div
                ref={wrapRef}
                className="pointer-events-none absolute left-0 top-0 origin-top-left will-change-transform"
                style={{ opacity: 0 }}
            >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/logo.png" alt ="" draggable={false} className="block h-full w-full" />
            </div>
        </div>
    );
}