import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MoveMind – AI Chess Coach",
  description:
    "Upload your chess game and get coach-style explanations of your biggest mistakes.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#0a0e1a] text-slate-100">{children}</body>
    </html>
  );
}
