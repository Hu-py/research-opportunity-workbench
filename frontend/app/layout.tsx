import type { Metadata } from "next";
import "./globals.css";
export const metadata:Metadata={title:"Research Atlas | 科研机会工作台",description:"跨学科文献发现、研究智能体与持续演化的选题知识库"};
export default function RootLayout({children}:{children:React.ReactNode}){
  return <html lang="zh-CN"><body>{children}</body></html>;
}
