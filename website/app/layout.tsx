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
    "Falco 2.5 Refiner edition: local dictation for Linux with optional Phonon acceleration and streamed cleanup previews. Audio and text stay on your machine.",
  openGraph: {
    title: `Falco ${version}: local dictation for Linux`,
    description:
      "The Refiner edition adds optional Phonon acceleration and streamed cleanup previews. See the initial Linux benchmark and install Falco 2.5.",
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
