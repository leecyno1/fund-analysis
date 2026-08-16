import {
  BadgeCheck,
  Bookmark,
  Bot,
  BookOpenText,
  ChartNoAxesCombined,
  Compass,
  Database,
  GitCompareArrows,
  House,
  Tags,
  Users,
  type LucideIcon,
} from 'lucide-react'

export type FundWorkspaceNavigationItem = {
  href: string
  label: string
  shortLabel: string
  icon: LucideIcon
  matches: readonly string[]
}

export type FundWorkspaceNavigationGroup = {
  label: string
  items: readonly FundWorkspaceNavigationItem[]
}

export const fundWorkspaceNavigation: readonly FundWorkspaceNavigationGroup[] = [
  {
    label: '发现',
    items: [
      { href: '/', label: '研究概览', shortLabel: '概览', icon: House, matches: ['/'] },
      { href: '/discover', label: '基金浏览器', shortLabel: '浏览', icon: Compass, matches: ['/discover', '/funds', '/market', '/companies'] },
      { href: '/managers', label: '基金经理', shortLabel: '经理', icon: Users, matches: ['/managers'] },
    ],
  },
  {
    label: '研究',
    items: [
      { href: '/compare', label: '同类比较', shortLabel: '比较', icon: GitCompareArrows, matches: ['/compare'] },
      { href: '/evaluation', label: '评价与分类', shortLabel: '评价', icon: BadgeCheck, matches: ['/evaluation'] },
      { href: '/research', label: '调研纪要', shortLabel: '纪要', icon: BookOpenText, matches: ['/research', '/reports'] },
      { href: '/analysis/advanced', label: '业绩归因', shortLabel: '归因', icon: ChartNoAxesCombined, matches: ['/analysis/advanced', '/barra', '/brinson'] },
    ],
  },
  {
    label: '我的',
    items: [
      { href: '/watchlist', label: '自选与候选', shortLabel: '自选', icon: Bookmark, matches: ['/watchlist'] },
      { href: '/analysis', label: 'AI 分析', shortLabel: 'AI', icon: Bot, matches: ['/analysis'] },
      { href: '/recommendations', label: '候选基金', shortLabel: '候选', icon: Tags, matches: ['/recommendations'] },
    ],
  },
]

export const fundWorkspaceDataNavigation: FundWorkspaceNavigationItem = {
  href: '/sync',
  label: '数据与方法',
  shortLabel: '数据',
  icon: Database,
  matches: ['/sync', '/evidence-coverage'],
}

export function isFundWorkspaceItemActive(
  pathname: string,
  item: FundWorkspaceNavigationItem,
) {
  return item.matches.some((match) => (
    match === '/'
      ? pathname === '/'
      : pathname === match || pathname.startsWith(`${match}/`)
  ))
}

export function currentFundWorkspaceItem(pathname: string) {
  const allItems = [
    ...fundWorkspaceNavigation.flatMap((group) => group.items),
    fundWorkspaceDataNavigation,
  ]
  return allItems.find((item) => isFundWorkspaceItemActive(pathname, item))
}
