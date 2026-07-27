import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "基金研究系统",
  description: "机构基金研究、同类横评、经理评价、持仓画像与证据台账工作台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className="h-full antialiased"
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
