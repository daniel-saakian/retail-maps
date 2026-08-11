import type { Metadata } from "next";
import { Suspense } from "react";
import { Playfair_Display, Inter, IBM_Plex_Mono } from "next/font/google";
import "./globals.css"
import NavBar from "@/components/NavBar";
import AutoSignOut from "@/components/AutoSignOut";
import WelcomeToast from "@/components/WelcomeToast";
import { JobsProvider } from "@/lib/JobsContext";

const playfair = Playfair_Display({
    subsets: ["latin"],
    variable: "--font-display",
    weight: ["600", "700"]
});

const inter = Inter({
    subsets: ["latin"],
    variable: "--font-sans",
});

const plexMono = IBM_Plex_Mono({
    subsets: ["latin"],
    weight: ["400", "500"],
    variable: "--font-mono",
});

export const metadata: Metadata = {
    title: "Plaza Finder | Stone Commercial",
    description: "Search cities for major retail plazas",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en" className={`${playfair.variable} ${inter.variable} ${plexMono.variable}`}>
            <body className="min-h-screen bg-paper font-sans text-ink antialiased">
                <JobsProvider>
                    <NavBar />
                    <Suspense fallback={null}>
                        <WelcomeToast />
                    </Suspense>
                    <AutoSignOut />
                    {children}
                </JobsProvider>
            </body>
        </html>
    )
}