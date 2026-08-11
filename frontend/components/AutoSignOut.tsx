"use client";

import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";

const IDLE_LIMIT_MS = 30 * 60 * 1000;
const ACTIVITY_EVENTS = ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "click"];

export default function AutoSignOut() {
    const pathname = usePathname();
    const router = useRouter();
    const [idle, setIdle] = useState(false);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        if (pathname.startsWith("/login")) return;

        function resetTimer() {
            if (timerRef.current) clearTimeout(timerRef.current);
            timerRef.current = setTimeout(async () => {
                const supabase = createClient();
                await supabase.auth.signOut();
                setIdle(true);
            }, IDLE_LIMIT_MS);
        }

        ACTIVITY_EVENTS.forEach((evt) => window.addEventListener(evt, resetTimer));
        resetTimer();

        return () => {
            ACTIVITY_EVENTS.forEach((evt) => window.removeEventListener(evt, resetTimer));
            if (timerRef.current) clearTimeout(timerRef.current);
        };
    }, [pathname]);

    if (!idle) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-sm">
            <div className="relative w-full max-w-sm rounded-xl border border-line bg-white p-6 text-center shadow-lg">
                <button
                    onClick={() => router.push("/login")}
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