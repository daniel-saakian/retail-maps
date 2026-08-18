"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

const IDLE_LIMIT_MS = 30 * 60 * 1000;
const CHECK_INTERVAL_MS = 15*1000;
const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "click"];

export default function AutoSignOut() {
    const pathname = usePathname();
    const [idle, setIdle] = useState(false);
    const lastActivityRef = useRef<number>(Date.now());
    const signedOutRef = useRef(false);

    useEffect(() => {
        if (pathname.startsWith("/login")) return;

        lastActivityRef.current = Date.now();
        signedOutRef.current = false;

        function markActive() {
            lastActivityRef.current = Date.now();
        }

        async function checkIdle() {
            if (signedOutRef.current) return;
            const elapsed = Date.now() - lastActivityRef.current;
            if (elapsed >= IDLE_LIMIT_MS) {
                signedOutRef.current = true;
                const supabase = createClient();
                await supabase.auth.signOut();
                setIdle(true);
            }
        }








        ACTIVITY_EVENTS.forEach((evt) => window.addEventListener(evt, markActive));
        document.addEventListener("visibilitychange",checkIdle)
        const interval = setInterval(checkIdle, CHECK_INTERVAL_MS);

        return () => {
            ACTIVITY_EVENTS.forEach((evt) => window.removeEventListener(evt, markActive));
            document.removeEventListener("visibilitychange", checkIdle);
            clearInterval(interval);
        };
    }, [pathname])

    if (!idle) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-sm">
            <div className="relative w-full max-w-sm rounded-xl border border-line bg-white p-6 text-center shadow-lg">
                <button
                    onClick={() => {
                        setIdle(false);
                        window.location.href = "/login";
                    }}
                    aria-label="Close"
                    className="absolute right-3 top-3 rounded p-1 text-charcoal hover:bg-paper-dim hover:text-ink"
                >
                    x
                </button>
                <p className="font-display text-lg font-semibold text-ink">Signed out</p>
                <p className="mt-2 text-sm text-charcoal">
                    You were signed out after 30 minutes of inactivity.
                </p>
            </div>
        </div>
    );
}