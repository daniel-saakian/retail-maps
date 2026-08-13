"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

const transition_ms = 300;
const welcome_hold_ms = 2000;
const goodbye_hold_ms = 6500;

export default function WelcomeToast() {
    const searchParams = useSearchParams();
    const pathname = usePathname();
    const router = useRouter();
    const [mounted, setMounted] = useState(false);
    const [visible, setVisible] = useState(false);
    const [message, setMessage] = useState("Signed in");

    useEffect(() => {
        const isWelcome = searchParams.get("welcome") === "1";
        const isGoodbye = searchParams.get("goodbye") === "1";
        if (!isWelcome && !isGoodbye) return;
        setMessage(isWelcome ? "Signed in" : "Signed out");

        const holdMs = isWelcome ? welcome_hold_ms : goodbye_hold_ms;

        setMounted(true);
        const enter = requestAnimationFrame(() => setVisible(true));

        const hideTimer = setTimeout(() => setVisible(false), transition_ms+holdMs);
        const cleanupTimer = setTimeout(() => {
            setMounted(false);
            const params = new URLSearchParams(searchParams.toString());
            params.delete("welcome");
            params.delete("goodbye");
            const query = params.toString();
            router.replace(pathname + (query ? `?${query}` : ""));
        }, transition_ms + holdMs + transition_ms);

        return () => {
            cancelAnimationFrame(enter);
            clearTimeout(hideTimer);
            clearTimeout(cleanupTimer);
        };
    }, [searchParams]);

    if (!mounted) return null;

    return (
        <div
            className={`fixed left-1/2 top-0 z-50 -translate-x-1/2 transition-all duration-300 ease-out ${
                visible ? "translate-y-4 opacity-100" : "-translate-y-full opacity-0"
            }`}
        >
            <div className="flex items-center gap-2 rounded-b-lg border border-t-0 border-line bg-ink px-5 py-2.5 text-sm font-medium text-white shadow-md">
                <span className="h-2 w-2 rounded-full bg-sky" />
                {message}
            </div>
        </div>
    );
}