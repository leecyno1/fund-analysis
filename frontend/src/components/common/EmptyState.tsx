import { ReactNode } from 'react'
import { Inbox, Search, FileText, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

interface EmptyStateProps {
  type?: 'default' | 'search' | 'data' | 'error'
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

const icons = {
  default: Inbox,
  search: Search,
  data: FileText,
  error: AlertCircle,
}

export function EmptyState({
  type = 'default',
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  const Icon = icons[type]

  return (
    <div className={cn('flex flex-col items-center justify-center py-16 px-4', className)}>
      <div className="bg-slate-50 rounded-full p-4 mb-4">
        <Icon className="w-10 h-10 text-slate-300" />
      </div>
      <h3 className="text-base font-semibold text-slate-700 mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-slate-500 text-center max-w-sm mb-4">
          {description}
        </p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
