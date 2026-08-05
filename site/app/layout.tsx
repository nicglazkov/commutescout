import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";

// Self-hosted by Next's font optimizer at build time. This is the same
// Inter family the map app self-hosts from /static/fonts/Inter-normal.woff2,
// loaded here through next/font instead so the site build and dev server
// don't depend on the Python app's static routes being reachable.
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  // Needed for og:image/twitter:image to resolve to an absolute URL: pages
  // that reference /static/shots/og.png (same-origin, served by the Python
  // app) would otherwise resolve against Next's localhost:3000 dev default
  // in the exported HTML. Every page metadata export is on this domain.
  metadataBase: new URL("https://commutescout.com"),
  title: "CommuteScout",
  description:
    "Live California road conditions: incidents, closures, and chain control from CHP, Caltrans, and the state DOTs.",
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
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-cs-bg text-cs-ink">
        <SiteHeader />
        <main className="flex-1">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
