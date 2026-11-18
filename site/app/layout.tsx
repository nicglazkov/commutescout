import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans, Manrope } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";

// Self-hosted by Next's font optimizer at build time, so no page asks
// Google for fonts at runtime. Manrope is the Night Drive face (marketing
// pages); IBM Plex Sans and Mono are the Blueprint faces (developer, API
// and MCP pages), and Plex Mono also sets code and the small mono labels
// on every page. globals.css picks between them per skin.
const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
});
const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});
const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

// Browser chrome color on phones: Day Drive's page color. ThemeToggle
// switches it to the night color when a visitor is on Night Drive.
export const viewport: Viewport = { themeColor: "#f4f3ef" };

export const metadata: Metadata = {
  // Needed for og:image/twitter:image to resolve to an absolute URL: pages
  // that reference /static/shots/og.png (same-origin, served by the Python
  // app) would otherwise resolve against Next's localhost:3000 dev default
  // in the exported HTML. Every page metadata export is on this domain.
  metadataBase: new URL("https://commutescout.com"),
  title: "CommuteScout",
  description:
    "Live road conditions across 37 states: incidents, closures, chain controls, cameras, and wildfires from official agency feeds.",
  // The four legacy app pages (map/watch/trip/admin.html) already use
  // <link rel="icon" href="/logo.svg">, served by the Starlette app from
  // src/ca_roads_demo/static/logo.svg (see the "/logo.svg" route in
  // app.py). Pointing the site's icon there too, ahead of the
  // app/favicon.ico fallback, gives every page the crisp brand SVG
  // instead of create-next-app's default icon.
  icons: {
    icon: [
      { url: "/logo.svg", type: "image/svg+xml" },
      { url: "/favicon.ico", sizes: "any" },
    ],
    // iOS home-screen icon. The legacy app pages already point at this
    // file; without it here, adding a marketing page to the home screen
    // used a screenshot, and /apple-touch-icon.png (the path iOS probes
    // by default) 404'd.
    apple: [{ url: "/static/icon-192.png", sizes: "192x192" }],
  },
  // The four legacy app pages ship the manifest; the marketing pages did
  // not, so an install prompt on the homepage had no app identity.
  manifest: "/manifest.webmanifest",
};

// Organization and WebSite schema, emitted once for the whole site. The
// map page carries its own WebApplication block; before this, none of
// the eight marketing pages had any structured data at all, so search
// engines had no machine-readable statement of what this site is or who
// runs it.
const SITE_SCHEMA = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://commutescout.com/#org",
      name: "CommuteScout",
      url: "https://commutescout.com",
      logo: "https://commutescout.com/logo.svg",
      description:
        "Live road conditions read from official state transportation "
        + "agency feeds.",
    },
    {
      "@type": "WebSite",
      "@id": "https://commutescout.com/#site",
      url: "https://commutescout.com",
      name: "CommuteScout",
      publisher: { "@id": "https://commutescout.com/#org" },
    },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${manrope.variable} ${plexSans.variable} ${plexMono.variable} h-full antialiased`}
      // The theme script below may set data-theme before React hydrates.
      suppressHydrationWarning
    >
      <head>
        {/* Theme, before first paint. Light is the default for everyone;
            only a stored choice from the header toggle switches to dark.
            Blocking and inline on purpose: run later and a dark-mode
            visitor would see a light flash. Wrapped in try because
            storage access can throw (private mode, blocked site data). */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              'try{if(localStorage.getItem("nd-theme")==="dark")document.documentElement.dataset.theme="dark"}catch(e){}',
          }}
        />
        <script
          type="application/ld+json"
          // SITE_SCHEMA is a build-time literal, so nothing user-supplied
          // reaches this string. The "<" escape is belt and braces: it
          // keeps a future dynamic field from being able to close the
          // script tag, which is the one way JSON-LD turns into an
          // injection point.
          dangerouslySetInnerHTML={{
            __html: JSON.stringify(SITE_SCHEMA).replace(/</g, "\\u003c"),
          }}
        />
        {/* Cloudflare Web Analytics: cookieless RUM, disclosed on the
            privacy page. The token is the public site tag of the
            commutescout.com property the admin analytics panel reads
            (CLOUDFLARE_SITE_TAG). Static export renders this tag
            directly, so it never touches React-managed DOM. */}
        <script
          defer
          src="https://static.cloudflareinsights.com/beacon.min.js"
          data-cf-beacon={'{"token": "d2d77aff6dfe4462b09ca501c9151de4"}'}
        />
      </head>
      <body className="flex min-h-full flex-col bg-cs-bg text-cs-ink">
        {/* Skip link: first focusable element in the body, invisible until
            keyboard focus lands on it (Tailwind's sr-only clips it
            off-screen; focus:not-sr-only restores normal layout on
            :focus). Jumps past SiteHeader's brand/nav/CTA straight to
            #main, the landmark below. */}
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-cs-sky focus:px-4 focus:py-2 focus:text-sm focus:font-medium focus:text-cs-on-sky focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cs-sky"
        >
          Skip to main content
        </a>
        <SiteHeader />
        <main id="main" className="flex-1">
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
