import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/lib/auth/AuthContext";
import { ProjectContextProvider } from "@/lib/context/ProjectContext";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "SpecForge AI",
  description: "Requirements-to-Spec guided workflow portal",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)]">
        <AuthProvider>
          <ProjectContextProvider>
            {children}
          </ProjectContextProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
