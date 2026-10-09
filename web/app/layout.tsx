import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Transcript OCR Studio · KMITL",
  description: "อ่าน ตรวจ และค้นข้อมูลผลการเรียนจาก Transcript",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="th"><body>{children}</body></html>;
}
