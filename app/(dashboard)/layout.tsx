import Link from 'next/link'
import { TrendingUp, Users, FileText, BarChart3, RefreshCw, Globe2, ClipboardCheck, GitCompareArrows, Filter } from 'lucide-react'

const navigationItems = [
  {
    href: '/market',
    icon: Globe2,
    label: '选基金',
    description: '全市场研究库',
  },
  {
    href: '/funds',
    icon: TrendingUp,
    label: '基金库',
    description: '基础资料与详情',
  },
  {
    href: '/analysis/comparison',
    icon: GitCompareArrows,
    label: '基金对比',
    description: '同类横评',
  },
  {
    href: '/managers',
    icon: Users,
    label: '基金经理',
    description: '任期与代表作',
  },
  {
    href: '/reports',
    icon: FileText,
    label: '研究报告',
    description: '报告库与复用',
  },
  {
    href: '/evidence-coverage',
    icon: ClipboardCheck,
    label: '数据证据',
    description: '覆盖率与缺口',
  },
  {
    href: '/analysis',
    icon: BarChart3,
    label: '基金研究',
    description: '单基金分析',
  },
  {
    href: '/screening',
    icon: Filter,
    label: '研究筛选',
    description: '方法论筛选',
  },
  {
    href: '/sync',
    icon: RefreshCw,
    label: '数据接入',
    description: '更新与诊断',
  },
]

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* 顶部导航栏 */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center">
              <h1 className="text-xl font-bold text-gray-900">
                基金研究系统
              </h1>
            </div>
            <nav className="flex space-x-8">
              <Link
                href="/overview"
                className="text-gray-600 hover:text-gray-900 px-3 py-2 text-sm font-medium"
              >
                首页
              </Link>
            </nav>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* 侧边栏 */}
        <aside className="w-64 bg-white border-r border-gray-200 min-h-[calc(100vh-4rem)] sticky top-16">
          <nav className="p-4 space-y-1">
            {navigationItems.map((item) => {
              const Icon = item.icon
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className="flex items-center px-4 py-3 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                  title={item.description}
                >
                  <Icon className="w-5 h-5 mr-3" />
                  <span className="leading-tight">
                    <span className="block text-sm font-medium">{item.label}</span>
                    <span className="block text-xs text-gray-400">{item.description}</span>
                  </span>
                </Link>
              )
            })}
          </nav>
        </aside>

        {/* 主内容区 */}
        <main className="flex-1 p-8">
          {children}
        </main>
      </div>
    </div>
  )
}
