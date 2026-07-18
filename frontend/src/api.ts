import type { Collection, Document, Page, Paginated, SearchResult } from './types'

export const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`, { headers: { Accept: 'application/json' } })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json()
}

export const api = {
  collections: () => request<Paginated<Collection>>('/collections/?page_size=100'),
  collection: (slug: string) => request<Collection>(`/collections/${slug}/`),
  documents: (params = '') => request<Paginated<Document>>(`/documents/?page_size=100${params ? `&${params}` : ''}`),
  document: (id: string) => request<Document>(`/documents/${id}/`),
  pages: (id: string) => request<Page[]>(`/documents/${id}/pages/`),
  search: (params: URLSearchParams) => request<Paginated<SearchResult>>(`/search/?${params}`),
  stats: () => request<{ totals: Record<string, number>; recent_documents: Document[] }>('/statistics/'),
  entity: (slug: string) => request<any>(`/entities/${slug}/`),
  claims: (slug: string) => request<any>(`/claims/${slug}/`),
  sourceDownload: (id: number) => `${API}/source-files/${id}/download/`,
}
