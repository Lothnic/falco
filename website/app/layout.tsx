import type { Metadata, Viewport } from "next";
import { Archivo, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { version } from "./release";

const archivo = Archivo({
  variable: "--font-archivo",
  subsets: ["latin"],
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

const themeScript = `(function(){try{var t=localStorage.getItem("falco-theme");if(t==="light"||t==="dark"){document.documentElement.dataset.theme=t}}catch(e){}})();`;

export const metadata: Metadata = {
  title: `Falco ${version}: local dictation for Linux`,
  description:
    "Falco 2.6.2: local dictation for Linux with spoken self-corrections, selected-text rewrites and local drafting. Audio and text stay on your machine.",
  openGraph: {
    title: `Falco ${version}: local dictation for Linux`,
    description:
      "Correct yourself while speaking and keep the final wording. Install Falco 2.6.2 for local dictation on Linux.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#0b2352",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className={`${archivo.variable} ${plexMono.variable}`}>{children}</body>
    </html>
  );
}
