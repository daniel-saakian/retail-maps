"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

export default function WelcomeToast() {
    const searchParams = useSearchParams();
    const pathname = usePathname();
    const router = useRouter();
    const [mounted, setMounted] = useState(false);
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        if (searchParams.get("welcome") !== "1") return;

        setMounted(true);
        const enter = requestAnimationFrame(() => setVisible(true));

        const hideTimer = setTimeout(() => setVisible(false), 300+2000);
        const cleanupTimer = setTimeout(() => {
            setMounted(false);
            const params = new URLSearchParams(searchParams.toString());
            params.delete("welcome");
            const query = params.toString();
            router.replace(pathname + (query ? `${query}` : ""));
        }, 300 + 2000 + 300);

        return () => {
            cancelAnimationFrame(enter);
            clearTimeout(hideTimer);
            clearTimeout(cleanupTimer);
        };
    }, []);

    if (!mounted) return null;

    return (
        <div
            className={`fixed left-1/2 top-0 z-50 -translate-x-1/2 transition-all duration-300 ease-out ${
                visible ? "translate-y-4 opacity-100" : "-translate-y-full opacity-0"
            }`}
        >
            <div className="flex items-center gap-2 rounded-b-lg border border-t-0 border-line bg-ink px-5 py-2.5 text-sm font-medium text-white shadow-md">
                <span className="h-2 w-2 rounded-full bg-sky" />
                Signed in
            </div>
        </div>
    );
}