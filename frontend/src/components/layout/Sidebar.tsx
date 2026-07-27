'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard, BarChart3, Users, Filter,
  FileText, Shield, BarChart2, PieChart, GitCompare, Star
} from 'lucide-react'
import { cn } from '@/lib/utils'

const navItems = [
  { href: '/', label: '首页总览', icon: LayoutDashboard },
  { href: '/funds', label: '基金列表', icon: BarChart3 },
  { href: '/managers', label: '基金经理', icon: Users },
  { href: '/screening', label: '基金筛选', icon: Filter },
  { href: '/compare', label: '基金对比', icon: GitCompare },
  { href: '/favorites', label: '我的收藏', icon: Star },
  { href: '/research', label: '调研报告库', icon: FileText },
  { href: '/barra', label: 'Barra分析', icon: BarChart2 },
  { href: '/brinson', label: '归因分析', icon: PieChart },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-slate-900 text-white flex flex-col z-50">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-slate-700/50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-500 rounded-lg flex items-center justify-center">
            <Shield className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="font-bold text-sm">基金经理评价系统</div>
            <div className="text-xs text-slate-400">Fund Analysis v2.0</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href))
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all',
                isActive
                  ? 'bg-blue-500/20 text-blue-400'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              )}
            >
              <item.icon className={cn('w-4 h-4', isActive ? 'text-blue-400' : '')} />
              {item.label}
            </Link>
          )
        })}
      </nav>

      {/* Bottom */}
      <div className="px-3 py-4 border-t border-slate-700/50">
        <div className="px-3 py-2">
          <div className="text-xs text-slate-500">数据来源：Tushare</div>
          <div className="text-xs text-slate-500 mt-0.5">API: 127.0.0.1:8005</div>
        </div>
      </div>
    </aside>
  )
}
