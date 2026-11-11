import type { Metadata, Viewport } from "next";
import { Archivo, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

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
  title: "Falco: local dictation for Linux",
  description:
    "Hold a key, speak, and clean text appears in the app you are using. Falco runs speech recognition and optional cleanup on your Linux machine.",
  openGraph: {
    title: "Falco: local dictation for Linux",
    description:
      "Local dictation for Linux. Hold a key, speak, and the words land in the focused app.",
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
