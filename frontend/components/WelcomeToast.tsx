"use client";
 
import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useJobs } from "@/lib/JobsContext";
 
const TRANSITION_MS = 300;
const WELCOME_HOLD_MS = 2000;
const GOODBYE_HOLD_MS = 6500;
 
export default function WelcomeToast() {
    const searchParams = useSearchParams();
    const pathname = usePathname();
    const router = useRouter();
    const { me } = useJobs();
    const [mounted, setMounted] = useState(false);
    const [visible, setVisible] = useState(false);
    const [kind, setKind] = useState<"welcome" | "goodbye" | null>(null);
 
    useEffect(() => {
        const isWelcome = searchParams.get("welcome") === "1";
        const isGoodbye = searchParams.get("goodbye") === "1";
        if (!isWelcome && !isGoodbye) return;
        setKind(isWelcome ? "welcome" : "goodbye");
 
        const holdMs = isWelcome ? WELCOME_HOLD_MS : GOODBYE_HOLD_MS;
 
        setMounted(true);
        const enter = requestAnimationFrame(() => setVisible(true));
 
        const hideTimer = setTimeout(() => setVisible(false), TRANSITION_MS + holdMs);
        const cleanupTimer = setTimeout(() => {
            setMounted(false);
            const params = new URLSearchParams(searchParams.toString());
            params.delete("welcome");
            params.delete("goodbye");
            const query = params.toString();
            router.replace(pathname + (query ? `?${query}` : ""));
        }, TRANSITION_MS + holdMs + TRANSITION_MS);
 
        return () => {
            cancelAnimationFrame(enter);
            clearTimeout(hideTimer);
            clearTimeout(cleanupTimer);
        };
    }, [searchParams]);
 
    if (!mounted || !kind) return null;
    const message =
        kind === "welcome"
            ? me?.first_name
                ? `Signed in as ${me.first_name}`
                : "Signed in"
            : "Signed out";
 
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