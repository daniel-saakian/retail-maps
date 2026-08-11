import type { Config } from "tailwindcss";

const config: Config = {
    content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
    theme: {
        extend: {
            colors: {
                ink: "#1B355E",
                "ink-2": "#152A4A",
                sky: "#2AA7DE",
                brass: "#B8934A",
                charcoal: "#4B4B4B",
                paper: "#FBF8F2",
                "paper-dim": "#F3EEE3",
                line: "#E4DDC9"
            },
            fontFamily: {
                display: ["var(--font-display)", "Georgia", "serif"],
                sans: ["var(--font-sans)", "Helvetica", "Arial", "sans-serif"],
                mono: ["var(--font-mono)", "ui-monospace", "monospace"]
            },
        },
    },
    plugins: []
};
export default config