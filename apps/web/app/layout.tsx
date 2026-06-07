import type { ReactNode } from "react";
import "./globals.css";

export const metadata = { title: "BLAST-RADIUS", description: "Multi-agent infra-change cockpit" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
