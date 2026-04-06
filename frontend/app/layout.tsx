import type { ReactNode } from "react";
import Link from "next/link";
import "./globals.css";

export const metadata = {
  title: "Claims Adjudication",
  description: "AI-assisted OPD claims adjudication system",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="app">
          <header className="topbar">
            <div className="topbar-inner">
              <div className="brand">
                <div className="logo" aria-hidden="true" />
                <div>
                  <h1>Claims Adjudication</h1>
                  <div className="muted" style={{ fontSize: 12 }}>OPD • AI-assisted extraction • deterministic rules</div>
                </div>
              </div>
              <nav className="nav">
                <Link href="/">Home</Link>
                <Link href="/submit-claim">Submit Claim</Link>
              </nav>
            </div>
          </header>
          <div className="container">{children}</div>
          <footer className="footer">Built for the Plum OPD adjudication assignment • Deterministic decisions with optional LLM-assisted understanding</footer>
        </div>
      </body>
    </html>
  );
}
