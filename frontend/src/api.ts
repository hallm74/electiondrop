import type { Collection, Document, Page, Paginated, SearchResult, Topic } from './types'

export const API = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')

const RETRYABLE_STATUS = new Set([429, 502, 503, 504])
const loadingSubscribers = new Set<() => void>()
let activeRequests = 0
let loadingVisible = false
let loadingTimer: number | undefined

export function subscribeApiLoading(callback: () => void) {
  loadingSubscribers.add(callback)
  return () => loadingSubscribers.delete(callback)
}

export function getApiLoading() {
  return loadingVisible
}

function notifyLoading() {
  loadingSubscribers.forEach(callback => callback())
}

function beginRequest() {
  activeRequests += 1
  if (activeRequests === 1) {
    loadingTimer = window.setTimeout(() => {
      if (activeRequests > 0) {
        loadingVisible = true
        notifyLoading()
      }
    }, 350)
  }
}

function endRequest() {
  activeRequests = Math.max(0, activeRequests - 1)
  if (activeRequests === 0) {
    if (loadingTimer !== undefined) window.clearTimeout(loadingTimer)
    loadingTimer = undefined
    if (loadingVisible) {
      loadingVisible = false
      notifyLoading()
    }
  }
}

async function request<T>(path: string): Promise<T> {
  beginRequest()
  let lastError: unknown
  try {
    for (let attempt = 0; attempt < 5; attempt += 1) {
      let response: Response | undefined
      try {
        response = await fetch(`${API}${path}`, { headers: { Accept: 'application/json' } })
      } catch (error) {
        lastError = error
      }
      if (response) {
        if (response.ok) return response.json()
        const responseError = new Error(`Request failed: ${response.status}`)
        if (!RETRYABLE_STATUS.has(response.status)) throw responseError
        lastError = responseError
      }
      if (attempt < 4) await new Promise(resolve => window.setTimeout(resolve, 500 * (2 ** attempt)))
    }
    throw lastError instanceof Error ? lastError : new Error('Request failed')
  } finally {
    endRequest()
  }
}

export const api = {
  collections: () => request<Paginated<Collection>>('/collections/?page_size=100'),
  collection: (slug: string) => request<Collection>(`/collections/${slug}/`),
  documents: (params = '') => request<Paginated<Document>>(`/documents/?page_size=100${params ? `&${params}` : ''}`),
  document: (id: string) => request<Document>(`/documents/${id}/`),
  pages: (id: string) => request<Page[]>(`/documents/${id}/pages/`),
  search: (params: URLSearchParams) => request<Paginated<SearchResult>>(`/search/?${params}`),
  stats: () => request<{ totals: Record<string, number>; recent_documents: Document[] }>('/statistics/'),
  topics: () => request<Topic[]>('/topics/'),
  entity: (slug: string) => request<any>(`/entities/${slug}/`),
  claims: (slug: string) => request<any>(`/claims/${slug}/`),
  sourcePreview: (id: number) => `${API}/source-files/${id}/download/`,
  sourceDownload: (id: number) => `${API}/source-files/${id}/download/?download=1`,
}
