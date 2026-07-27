'use client'

import { useState, useEffect } from 'react'
import { Star, Trash2, ExternalLink } from 'lucide-react'
import Link from 'next/link'
import { getFavorites, removeFavorite, FavoriteItem } from '@/lib/favorites'

export default function FavoritesPage() {
  const [favorites, setFavorites] = useState<FavoriteItem[]>([])
  const [filter, setFilter] = useState<'all' | 'fund' | 'manager'>('all')

  useEffect(() => {
    setFavorites(getFavorites())
  }, [])

  const handleRemove = (id: string) => {
    removeFavorite(id)
    setFavorites(getFavorites())
  }

  const filteredFavorites = favorites.filter(f => filter === 'all' || f.type === filter)

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-2">
            <Star className="w-8 h-8 text-yellow-500 fill-yellow-500" />
            我的收藏
          </h1>
          <p className="text-slate-500 mt-1">收藏的基金和基金经理</p>
        </div>
        <div className="flex gap-2">
          {(['all', 'fund', 'manager'] as const).map(type => (
            <button
              key={type}
              onClick={() => setFilter(type)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filter === type
                  ? 'bg-blue-500 text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {type === 'all' ? '全部' : type === 'fund' ? '基金' : '基金经理'}
            </button>
          ))}
        </div>
      </div>

      {filteredFavorites.length === 0 ? (
        <div className="bg-slate-50 rounded-xl border-2 border-dashed border-slate-200 p-12 text-center">
          <Star className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <p className="text-slate-400">暂无收藏</p>
          <p className="text-sm text-slate-400 mt-1">在基金或基金经理详情页点击星标收藏</p>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {filteredFavorites.map(item => (
            <div key={item.id} className="bg-white rounded-xl shadow-sm border border-slate-100 p-5 hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      item.type === 'fund' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'
                    }`}>
                      {item.type === 'fund' ? '基金' : '经理'}
                    </span>
                  </div>
                  <h3 className="font-semibold text-slate-900 mb-1">{item.name}</h3>
                  {item.code && <p className="text-xs text-slate-400">{item.code}</p>}
                </div>
                <button
                  onClick={() => handleRemove(item.id)}
                  className="w-8 h-8 rounded-lg bg-slate-100 hover:bg-red-100 flex items-center justify-center transition-colors group"
                >
                  <Trash2 className="w-4 h-4 text-slate-400 group-hover:text-red-500" />
                </button>
              </div>
              <div className="flex items-center justify-between text-xs text-slate-400 mb-3">
                <span>收藏于 {new Date(item.addedAt).toLocaleDateString()}</span>
              </div>
              <Link
                href={item.type === 'fund' ? `/funds/${item.id}` : `/managers/${item.id}`}
                className="flex items-center justify-center gap-2 w-full py-2 bg-slate-50 hover:bg-slate-100 rounded-lg text-sm font-medium text-slate-700 transition-colors"
              >
                查看详情
                <ExternalLink className="w-4 h-4" />
              </Link>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
