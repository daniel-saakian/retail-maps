/** @type {import('next').NextConfig} */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const isDev = process.env.NODE_ENV !== "production";
 
const connectSrc = ["'self'", API_BASE, SUPABASE_URL].filter(Boolean).join(" ");
 
// 'unsafe-eval' is only needed for Next's dev-mode hot reload (Turbopack/webpack
// eval-based source maps) -- omitted entirely in production for a tighter policy.
const scriptSrc = isDev
    ? "'self' 'unsafe-inline' 'unsafe-eval'"
    : "'self' 'unsafe-inline'";
 
const csp = [
    `default-src 'self'`,
    `script-src ${scriptSrc}`,
    `style-src 'self' 'unsafe-inline'`,
    `img-src 'self' data: https:`,
    `font-src 'self' data:`,
    `connect-src ${connectSrc}`,
    `frame-src 'self' https://daniel-saakian.github.io`,
    `frame-ancestors 'none'`,
    `base-uri 'self'`,
    `form-action 'self'`,
    `object-src 'none'`,
].join("; ");
 
const securityHeaders = [
    { key: "Content-Security-Policy", value: csp },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];
 
const nextConfig = {
    ...(process.env.VERCEL ? {} : { turbopack: { root: __dirname } }),
    async headers() {
        return [
            {
                source: "/:path*",
                headers: securityHeaders,
            },
        ];
    },
};
 
module.exports = nextConfig;