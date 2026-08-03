import Link from 'next/link'
import { Users, FileText, RefreshCw, ClipboardCheck, GitCompareArrows, Filter, Landmark, ShieldCheck, BookOpenCheck, Radar } from 'lucide-react'

const navigationItems = [
  {
    href: '/mod/fund-research/overview',
    icon: Landmark,
    label: '研究总览',
    description: '九段式专业流程',
  },
  {
    href: '/mod/fund-research/selection',
    icon: Filter,
    label: '准入初筛',
    description: '全市场研究库',
  },
  {
    href: '/mod/fund-research/peer-comparison',
    icon: GitCompareArrows,
    label: '同类横评',
    description: 'Peer、基准与风格',
  },
  {
    href: '/mod/fund-research/due-diligence',
    icon: ShieldCheck,
    label: '尽调工作台',
    description: 'People、Process、ODD',
  },
  {
    href: '/mod/fund-research/monitoring',
    icon: Radar,
    label: '监控复核',
    description: '事件触发与论点漂移',
  },
  {
    href: '/mod/fund-research/methodology',
    icon: BookOpenCheck,
    label: '方法论',
    description: '来源、版本与审计',
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
    href: '/screening',
    icon: Filter,
    label: '筛选工具',
    description: '旧筛选器与模板',
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

      <div className="flex min-w-0">
        {/* 侧边栏 */}
        <aside className="sticky top-16 hidden min-h-[calc(100vh-4rem)] w-64 shrink-0 self-start border-r border-gray-200 bg-white lg:block">
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
        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  )
}
