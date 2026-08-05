import AppNavigation from '@/components/navigation/AppNavigation'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-screen bg-[#f7f8f5] text-[#1d2521]">
      <AppNavigation />
      <main className="mx-auto w-full max-w-[1440px] px-4 pb-28 pt-6 sm:px-6 lg:px-10 lg:pb-12 lg:pt-8">
        {children}
      </main>
    </div>
  )
}
