import type { Metadata } from "next";
import "./globals.css";
import Providers from "@/components/providers";

export const metadata: Metadata = {
  title: "InsightForge AI — Schema-Aware SQL Intelligence Workspace",
  description: "Explore schemas visually, write natural language queries to safe SQL, optimize query execution, and explain database plans in a secure schema-aware agentic environment.",
  keywords: ["SQL Intelligence", "Schema Explorer", "Natural Language to SQL", "SQL Optimizer", "Safe Database Client"],
  authors: [{ name: "InsightForge AI Team" }],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className="antialiased min-h-screen bg-background text-foreground">
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
