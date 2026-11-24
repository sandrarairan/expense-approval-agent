import type { Metadata } from "next";
import "@copilotkit/react-core/v2/styles.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "Expense Approval Agent · CopilotKit + Google ADK",
  description:
    "Frontend Next.js con CopilotKit v2 y protocolo AG-UI conectado a Expense Approval Agent (Google ADK 2.0).",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
