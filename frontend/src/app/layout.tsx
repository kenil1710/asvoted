import type { Metadata, Viewport } from "next";
import { Hanken_Grotesk, Literata, Martian_Mono } from "next/font/google";
import "./globals.css";
import { WalletProvider } from "@/components/WalletProvider";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";

const literata = Literata({ subsets: ["latin"], variable: "--font-literata", display: "swap" });
const hanken = Hanken_Grotesk({ subsets: ["latin"], variable: "--font-hanken", display: "swap" });
const martian = Martian_Mono({ subsets: ["latin"], variable: "--font-martian", display: "swap", weight: ["400", "500"] });

export const metadata: Metadata = {
  title: "AsVoted: did the Safe execute what holders voted for?",
  description: "AsVoted reads every action a DAO's Safe executed, checks it against the Snapshot proposal that passed, and keeps watching. Built on GenLayer.",
};

export const viewport: Viewport = {
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#eceff3" }, { media: "(prefers-color-scheme: dark)", color: "#10131f" }],
};

const themeScript = `try{var t=localStorage.getItem("asvoted-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${literata.variable} ${hanken.variable} ${martian.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen antialiased">
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-sheet focus:px-3 focus:py-2">Skip to content</a>
        <WalletProvider>
          <Header />
          <main id="main" className="mx-auto w-full max-w-6xl px-4 pb-20 sm:px-6">{children}</main>
          <Footer />
        </WalletProvider>
      </body>
    </html>
  );
}
