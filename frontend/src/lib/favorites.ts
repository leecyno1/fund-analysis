export interface FavoriteItem {
  id: string
  type: 'fund' | 'manager'
  name: string
  code?: string
  addedAt: number
}

const STORAGE_KEY = 'fund_favorites'

export const getFavorites = (): FavoriteItem[] => {
  if (typeof window === 'undefined') return []
  const stored = localStorage.getItem(STORAGE_KEY)
  return stored ? JSON.parse(stored) : []
}

export const addFavorite = (item: Omit<FavoriteItem, 'addedAt'>): void => {
  const favorites = getFavorites()
  if (favorites.find(f => f.id === item.id)) return
  favorites.push({ ...item, addedAt: Date.now() })
  localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites))
}

export const removeFavorite = (id: string): void => {
  const favorites = getFavorites().filter(f => f.id !== id)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites))
}

export const isFavorite = (id: string): boolean => {
  return getFavorites().some(f => f.id === id)
}

export const toggleFavorite = (item: Omit<FavoriteItem, 'addedAt'>): boolean => {
  if (isFavorite(item.id)) {
    removeFavorite(item.id)
    return false
  } else {
    addFavorite(item)
    return true
  }
}
