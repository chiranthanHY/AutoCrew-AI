import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeProvider";
import { Navbar } from "@/components/Navbar";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "AutoCrew AI — Multi-Agent Automation Platform",
    template: "%s | AutoCrew AI",
  },
  description:
    "AutoCrew AI orchestrates specialized AI agents — Planner, Researcher, Executor, Critic, and Verifier — to automate complex workflows end-to-end.",
  keywords: ["AI agents", "automation", "LangGraph", "Groq", "multi-agent", "workflow"],
  openGraph: {
    title: "AutoCrew AI — Multi-Agent Automation Platform",
    description: "From idea to delivery, powered by a crew of specialized AI agents.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning className={`dark ${inter.variable} ${mono.variable}`}>
      <body className="font-sans antialiased min-h-screen bg-background text-foreground">
        <ThemeProvider>
          <Navbar />
          <main>{children}</main>
        </ThemeProvider>
      </body>
    </html>
  );
}
