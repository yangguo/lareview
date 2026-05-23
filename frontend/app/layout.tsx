import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "LA Review Agent",
  description: "Access-rights and HR status reconciliation"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "sans-serif", margin: 24 }}>{children}</body>
    </html>
  );
}
