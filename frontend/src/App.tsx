import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react'
import { Link, NavLink, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, BookOpen, Check, ChevronRight, Copy, Download, ExternalLink, FileSearch, Filter, Menu, Search, ShieldCheck, X } from 'lucide-react'
import { api, getApiLoading, subscribeApiLoading } from './api'
import type { Collection, Document, Page, SearchResult, Topic } from './types'

const collectionFallback: Collection[] = [
  { id: 1, slug: 'vulnerabilities', code: 'VULN', title: 'Vulnerabilities in Electronic Voting and Ballot-Counting Systems', description: 'Primary-source records concerning reported technical vulnerabilities in election technology. A vulnerability does not, by itself, establish exploitation or an altered vote.', source_url: '', display_order: 1, document_count: 0, page_count: 0 },
  { id: 2, slug: 'china-voter-data', code: 'CHINA', title: 'China’s Acquisition and Exploitation of American Voter Data', description: 'Records concerning reported acquisition, access, or use of American voter data, with allegations and assessments labeled by source and review status.', source_url: '', display_order: 2, document_count: 0, page_count: 0 },
  { id: 3, slug: 'michigan-registration', code: 'MICH', title: 'Michigan Voter-Registration Investigation', description: 'Investigative records and correspondence concerning Michigan voter-registration activity. Registration applications, accepted registrations, ballots, charges, and convictions remain distinct evidence categories.', source_url: '', display_order: 3, document_count: 0, page_count: 0 },
  { id: 4, slug: 'noncitizen-rolls', code: 'NONCIT', title: 'Noncitizens on State Voter Rolls', description: 'Records concerning possible or confirmed noncitizen matches on voter rolls. Database matches are not presented as registrations or votes without source evidence.', source_url: '', display_order: 4, document_count: 0, page_count: 0 },
]

function useLoad<T>(loader: () => Promise<T>, deps: unknown[], fallback?: T) {
  const [data, setData] = useState<T | undefined>(fallback)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  useEffect(() => {
    let active = true
    setLoading(true)
    loader().then(value => { if (active) { setData(value); setError(false) } }).catch(() => { if (active) setError(true) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps
  return { data, loading, error }
}

function Header() {
  const [open, setOpen] = useState(false)
  return <>
    <div className="source-strip"><span>Public evidence browser</span><span>White House release · July 2026</span></div>
    <header className="site-header">
      <Link className="brand" to="/" aria-label="Election Release Archive home">
        <span className="brand-mark">ERA</span><span><strong>Election Release</strong><small>ARCHIVE</small></span>
      </Link>
      <button className="menu-button" onClick={() => setOpen(!open)} aria-label="Toggle navigation">{open ? <X /> : <Menu />}</button>
      <nav className={open ? 'open' : ''}>
        <NavLink to="/collections">Collections</NavLink><NavLink to="/search">Search documents</NavLink><a href="/about">Methodology</a>
      </nav>
    </header>
  </>
}

function Footer() {
  return <footer><div><strong>Election Release Archive</strong><p>A neutral evidence browser. Source text and editorial metadata are labeled separately.</p></div><div className="footer-links"><Link to="/collections">Collections</Link><Link to="/search">Search</Link><a href="/admin/">Reviewer access</a></div></footer>
}

function Layout({ children }: { children: React.ReactNode }) {
  const location = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [location.pathname])
  return <><Header /><main>{children}</main><Footer /></>
}

function SearchBar({ initial = '', compact = false }: { initial?: string; compact?: boolean }) {
  const [query, setQuery] = useState(initial)
  const navigate = useNavigate()
  return <form className={`search-bar ${compact ? 'compact' : ''}`} onSubmit={e => { e.preventDefault(); if (query.trim()) navigate(`/search?q=${encodeURIComponent(query.trim())}`) }}>
    <Search aria-hidden="true" /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search names, agencies, identifiers, or exact phrases" aria-label="Search the archive" /><button>Search archive</button>
  </form>
}

function ProvenanceBadge({ source }: { source: string }) {
  const labels: Record<string, string> = { printed: 'Printed in source', embedded: 'PDF metadata', inferred: 'Inferred', editorial: 'Editorial', imported: 'Imported filename' }
  return <span className={`provenance ${source}`}>{labels[source] || source}</span>
}

function HomePage() {
  const collections = useLoad(() => api.collections().then(x => x.results), [], collectionFallback)
  const stats = useLoad(api.stats, [], { totals: { source_files: 0, documents: 0, pages: 0, searchable_pages: 0 }, recent_documents: [] })
  const topics = useLoad(api.topics, [], [])
  const totals = stats.data?.totals || {}
  return <>
    <section className="hero">
      <div className="eyebrow"><span></span>THE JULY 2026 DOCUMENT RELEASE</div>
      <h1>Read the record.<br /><em>Trace every claim.</em></h1>
      <p className="hero-copy">Browse the original election-integrity documents, search page-level text, and follow claims to their precise source—with evidence categories kept distinct.</p>
      <SearchBar />
      <div className="trust-line"><ShieldCheck /><span>Original files preserved</span><span>Page-level citations</span><span>Editorial content labeled</span></div>
    </section>

    <section className="stats-band" aria-label="Archive statistics">
      {[['Source files', totals.source_files], ['Documents', totals.documents], ['Pages', totals.pages], ['Searchable pages', totals.searchable_pages]].map(([label, value]) => <div key={String(label)}><strong>{Number(value || 0).toLocaleString()}</strong><span>{label}</span></div>)}
      {stats.error && <small className="offline-note">Waiting for the local archive service</small>}
    </section>

    <TopicCloud topics={topics.data || []} />

    <section className="collections-section">
      <div className="section-heading"><div><span className="kicker">THE SOURCE COLLECTIONS</span><h2>Four bodies of evidence</h2></div><p>Each collection preserves its original source context while exposing document- and page-level records for review.</p></div>
      <div className="collection-grid">
        {(collections.data || collectionFallback).map((collection, i) => <Link to={`/collections/${collection.slug}`} className="collection-card" key={collection.slug}>
          <div className="collection-top"><span className="collection-number">0{i + 1}</span><span className="collection-code">WH–EI–{collection.code}</span></div>
          <h3>{collection.title}</h3><p>{collection.description}</p>
          <div className="card-meta"><span>{collection.document_count || 0} documents</span><span>{collection.page_count || 0} pages</span><ChevronRight /></div>
        </Link>)}
      </div>
    </section>

    <section className="distinctions">
      <div><span className="kicker light">READING THE RECORD</span><h2>Similar words can describe<br />very different evidence.</h2></div>
      <div className="distinction-flow">
        {['Vulnerability', 'Attempted intrusion', 'Successful intrusion', 'Altered outcome'].map((item, i) => <div key={item}><span>{String(i + 1).padStart(2, '0')}</span><strong>{item}</strong>{i < 3 && <ArrowRight />}</div>)}
      </div>
      <p>The archive does not collapse these categories. A vulnerable system is not proof of intrusion; a registration record is not proof of a counted ballot; an investigation is not a conviction.</p>
    </section>

    <section className="recent-section">
      <div className="section-heading"><div><span className="kicker">LATEST IN THE ARCHIVE</span><h2>Recently imported</h2></div><Link className="text-link" to="/search">Browse all documents <ArrowRight /></Link></div>
      {stats.data?.recent_documents?.length ? <div className="document-list">{stats.data.recent_documents.map(doc => <DocumentRow key={doc.stable_id} document={doc} />)}</div> : <EmptyArchive />}
    </section>
  </>
}

function TopicCloud({ topics }: { topics: Topic[] }) {
  const visible = topics.filter(topic => topic.document_count > 0)
  const maximum = Math.max(...visible.map(topic => topic.document_count), 1)
  return <section className="topic-cloud-section">
    <div className="topic-cloud-heading">
      <div><span className="kicker">FOLLOW THE LANGUAGE</span><h2>What keeps appearing<br /><em>in the record?</em></h2></div>
      <p>Topics are curated from the released material and sized by matching documents—not repetition on a single page. Select one to open every matching source page.</p>
    </div>
    <div className="topic-cloud" aria-label="Recurring archive topics">
      {visible.map((topic, index) => {
        const scale = Math.sqrt(topic.document_count / maximum)
        const size = 15 + scale * 35
        return <Link
          className={`topic-word ${topic.slug === 'burisma-ukraine' ? 'featured' : ''}`}
          style={{ fontSize: `${size}px` }}
          to={`/search?topic=${encodeURIComponent(topic.slug)}`}
          title={`${topic.document_count} documents · ${topic.mention_count} mentions`}
          key={topic.slug}
        ><span>{topic.label}</span><small>{topic.document_count}</small>{index < visible.length - 1 && <i>·</i>}</Link>
      })}
    </div>
    <div className="topic-cloud-note"><span></span>Size reflects matching documents <b>·</b> Counts update as OCR and review continue</div>
  </section>
}

function EmptyArchive() {
  return <div className="empty-state"><FileSearch /><div><h3>The shelves are ready for the source release.</h3><p>No documents have been imported yet. Once originals are added, they will appear here with hashes, page counts, and extraction status.</p></div></div>
}

function DocumentRow({ document }: { document: Document }) {
  return <Link className="document-row" to={`/documents/${document.stable_id}`}>
    <span className="file-icon">PDF</span><div className="document-row-main"><span className="mono">{document.stable_id}</span><h3>{document.title}</h3><p>{document.originating_agency || 'Agency not yet reviewed'} · {document.document_type || 'Document type pending'}</p></div><div className="document-row-end"><span>{document.document_date || 'Date not established'}</span><span>{document.page_count || document.end_page} pages</span><ChevronRight /></div>
  </Link>
}

function CollectionsIndex() {
  const { data } = useLoad(() => api.collections().then(x => x.results), [], collectionFallback)
  return <PageShell eyebrow="SOURCE COLLECTIONS" title="Browse the release" intro="Explore each body of evidence without losing the distinctions between primary-source language, agency assessments, allegations, and editorial context."><div className="collection-grid index">{(data || collectionFallback).map((c, i) => <Link to={`/collections/${c.slug}`} className="collection-card" key={c.slug}><div className="collection-top"><span className="collection-number">0{i + 1}</span><span className="collection-code">WH–EI–{c.code}</span></div><h3>{c.title}</h3><p>{c.description}</p><div className="card-meta"><span>{c.document_count || 0} documents</span><span>{c.page_count || 0} pages</span><ChevronRight /></div></Link>)}</div></PageShell>
}

function PageShell({ eyebrow, title, intro, children }: { eyebrow: string; title: string; intro: string; children: React.ReactNode }) {
  return <div className="page-shell"><section className="page-intro"><span className="kicker">{eyebrow}</span><h1>{title}</h1><p>{intro}</p></section>{children}</div>
}

function CollectionPage() {
  const { slug = '' } = useParams()
  const collection = useLoad(() => api.collection(slug), [slug], collectionFallback.find(c => c.slug === slug))
  const documents = useLoad(() => api.documents(`collection=${encodeURIComponent(slug)}`), [slug])
  const c = collection.data
  if (!c) return <NotFound />
  return <div className="page-shell">
    <div className="breadcrumbs"><Link to="/collections">Collections</Link><ChevronRight /><span>{c.code}</span></div>
    <section className="collection-hero"><span className="collection-code">WH–EI–{c.code}</span><h1>{c.title}</h1><p>{c.description}</p><div className="collection-stats"><span><strong>{c.document_count || 0}</strong> documents</span><span><strong>{c.page_count || 0}</strong> pages</span><span><strong>—</strong> date range</span></div></section>
    <div className="list-toolbar"><div><h2>Documents</h2><span>{documents.data?.count || 0} records</span></div><SearchBar compact /></div>
    <div className="document-list">{documents.data?.results?.length ? documents.data.results.map(doc => <DocumentRow document={doc} key={doc.stable_id} />) : <EmptyArchive />}</div>
  </div>
}

const filterOptions = [
  ['collection', 'Collection', ['', 'All collections'], ['vulnerabilities', 'System vulnerabilities'], ['china-voter-data', 'China & voter data'], ['michigan-registration', 'Michigan investigation'], ['noncitizen-rolls', 'Noncitizen rolls']],
  ['extraction_method', 'Text source', ['', 'Any text source'], ['embedded', 'Embedded text'], ['ocr', 'OCR text'], ['none', 'No searchable text']],
  ['reviewed', 'Review status', ['', 'Any review status'], ['true', 'Reviewed'], ['false', 'Unreviewed']],
]

function SearchPage() {
  const [params, setParams] = useSearchParams()
  const [draft, setDraft] = useState(params.get('q') || '')
  const result = useLoad(() => api.search(params), [params.toString()])
  const submit = (e: React.FormEvent) => { e.preventDefault(); const next = new URLSearchParams(params); draft ? next.set('q', draft) : next.delete('q'); next.delete('page'); setParams(next) }
  const setFilter = (key: string, value: string) => { const next = new URLSearchParams(params); value ? next.set(key, value) : next.delete(key); next.delete('page'); setParams(next) }
  return <div className="search-page">
    <section className="search-head"><span className="kicker light">SEARCH THE FULL RECORD</span><h1>Find the source page.</h1><form onSubmit={submit}><Search /><input value={draft} onChange={e => setDraft(e.target.value)} placeholder="Try an agency, identifier, location, or phrase" autoFocus /><button>Search</button></form></section>
    <div className="search-layout">
      <aside><div className="filter-title"><Filter /> Filter results</div>{filterOptions.map(([key, title, ...options]) => <label key={String(key)}>{title as string}<select value={params.get(key as string) || ''} onChange={e => setFilter(key as string, e.target.value)}>{(options as string[][]).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>)}<label>Date from<input type="date" value={params.get('date_from') || ''} onChange={e => setFilter('date_from', e.target.value)} /></label><label>Date to<input type="date" value={params.get('date_to') || ''} onChange={e => setFilter('date_to', e.target.value)} /></label>{[...params].length > 0 && <button className="clear-filters" onClick={() => { setDraft(''); setParams({}) }}><X /> Clear all</button>}</aside>
      <section className="results"><div className="results-header"><div><strong>{result.data?.count ?? 0}</strong> page-level results</div><span>Sorted by relevance</span></div>{result.loading ? <LoadingRows /> : result.data?.results.length ? result.data.results.map(item => <SearchResultCard result={item} query={params.get('q') || ''} key={item.stable_page_id} />) : <div className="no-results"><FileSearch /><h2>{params.get('q') ? 'No matching source pages' : 'Search across every page'}</h2><p>{result.error ? 'The archive service is not running yet. Start the backend to search imported records.' : params.get('q') ? 'Try a broader phrase or remove a filter.' : 'Enter a name, agency, identifier, place, or exact phrase above.'}</p></div>}</section>
    </div>
  </div>
}

function highlight(text: string, query: string) {
  if (!query.trim()) return text
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return text.split(new RegExp(`(${escaped})`, 'ig')).map((part, i) => part.toLowerCase() === query.toLowerCase() ? <mark key={i}>{part}</mark> : part)
}

function SearchResultCard({ result, query }: { result: SearchResult; query: string }) {
  return <Link className="result-card" to={result.page_url}><div className="result-kicker"><span>{result.collection_title}</span><span>{result.stable_page_id}</span></div><h2>{result.document_title}</h2><p className="excerpt">{highlight(result.excerpt, query)}</p><div className="result-meta"><span>{result.agency || 'Agency pending review'}</span><span>{result.document_date || 'Date not established'}</span><span className={`method ${result.extraction_method}`}>{result.extraction_method === 'ocr' ? 'OCR text' : result.extraction_method === 'embedded' ? 'Embedded text' : 'No text'}</span><span>Page {result.page_number}</span></div></Link>
}

function LoadingRows() { return <>{[1, 2, 3].map(x => <div className="loading-row" key={x}><span></span><span></span><span></span></div>)}</> }

function ApiWakeScreen() {
  const loading = useSyncExternalStore(subscribeApiLoading, getApiLoading, getApiLoading)
  if (!loading) return null
  return <div className="api-wake-screen" role="status" aria-live="polite" aria-label="The archive is waking up">
    <div className="wake-art" aria-hidden="true">
      <div className="wake-ring ring-one"></div><div className="wake-ring ring-two"></div>
      <div className="ballot-paper paper-one"><span></span><span></span><span></span></div>
      <div className="ballot-paper paper-two"><span></span><span></span><span></span></div>
      <div className="ballot-box"><i></i><b>ERA</b></div>
    </div>
    <span className="kicker light">WAKING THE PUBLIC RECORDS VAULT</span>
    <h2>Election secrets incoming<span className="wake-dots"><i>.</i><i>.</i><i>.</i></span></h2>
    <p>The archive took a quick power nap. Reassembling documents, citations, and suspiciously well-organized PDFs.</p>
  </div>
}

function PdfCanvas({ url, pageNumber, fallbackUrl, fallbackLoading }: { url: string; pageNumber: number; fallbackUrl?: string; fallbackLoading?: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [status, setStatus] = useState<'loading' | 'rendered' | 'failed'>('loading')
  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    async function render() {
      try {
        const pdfjs = await import('pdfjs-dist')
        pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString()
        const pdf = await pdfjs.getDocument({ url }).promise
        const page = await pdf.getPage(pageNumber)
        const viewport = page.getViewport({ scale: 1.35 })
        if (!canvas.current || cancelled) return
        canvas.current.width = viewport.width; canvas.current.height = viewport.height
        await page.render({ canvas: canvas.current, canvasContext: canvas.current.getContext('2d')!, viewport }).promise
        if (!cancelled) setStatus('rendered')
      } catch { if (!cancelled) setStatus('failed') }
    }
    render(); return () => { cancelled = true }
  }, [url, pageNumber])
  if (status === 'failed' && fallbackUrl) return <img src={fallbackUrl} alt={`Original page ${pageNumber}`} />
  if (status === 'failed' && fallbackLoading) return <div className="pdf-fallback"><BookOpen /><p>Loading preserved page preview…</p></div>
  if (status === 'failed') return <div className="pdf-fallback"><BookOpen /><p>Preview unavailable. The preserved original can still be downloaded.</p></div>
  return <canvas ref={canvas} aria-busy={status === 'loading'} />
}

function DocumentPage() {
  const { id = '', page = '1' } = useParams()
  const navigate = useNavigate()
  const document = useLoad(() => api.document(id), [id])
  const pages = useLoad(() => api.pages(id), [id], [])
  const currentNumber = Math.max(1, Number(page || 1))
  const current = pages.data?.find(p => p.logical_page_number === currentNumber)
  const doc = document.data
  if (!doc && !document.loading) return <NotFound />
  if (!doc) return <div className="document-loading"><LoadingRows /></div>
  const total = pages.data?.length || doc.page_count || doc.end_page
  const go = (next: number) => navigate(`/documents/${id}/pages/${Math.min(Math.max(next, 1), total)}`)
  return <div className="document-page">
    <div className="document-header"><div className="breadcrumbs"><Link to={`/collections/${doc.collection.slug}`}>{doc.collection.title}</Link><ChevronRight /><span>{doc.stable_id}</span></div><div className="document-title-row"><div><span className="mono">{doc.stable_id}</span><h1>{doc.title}</h1><ProvenanceBadge source={doc.title_source} /></div><a className="download-button" href={api.sourceDownload(doc.source_file)}><Download /> Original PDF</a></div><div className="document-facts"><span><small>Agency</small>{doc.originating_agency || 'Not established'} <ProvenanceBadge source={doc.agency_source} /></span><span><small>Date</small>{doc.document_date || 'Not established'} <ProvenanceBadge source={doc.date_source} /></span><span><small>Document type</small>{doc.document_type || 'Pending review'}</span><span><small>Source hash</small><code>{doc.source_sha256.slice(0, 12)}…</code></span></div></div>
    <div className="viewer-toolbar"><div><button onClick={() => go(currentNumber - 1)} disabled={currentNumber <= 1} aria-label="Previous page"><ArrowLeft /></button><span>Page <input value={currentNumber} onChange={e => go(Number(e.target.value))} aria-label="Current page" /> of {total}</span><button onClick={() => go(currentNumber + 1)} disabled={currentNumber >= total} aria-label="Next page"><ArrowRight /></button></div><button onClick={() => navigator.clipboard.writeText(window.location.href)}><Copy /> Copy page link</button></div>
    <div className="split-viewer">
      <section className="pdf-pane" aria-label="Original document page"><div className="paper"><PdfCanvas url={api.sourcePreview(doc.source_file)} pageNumber={currentNumber} fallbackUrl={current?.image_url} fallbackLoading={pages.loading} /></div></section>
      <section className="text-pane"><div className="text-pane-head"><div><span className="kicker">SEARCHABLE TRANSCRIPT</span><h2>{current?.stable_page_id || `${doc.stable_id}-P${String(currentNumber).padStart(3, '0')}`}</h2></div><span className={`method ${current?.extraction_method || 'none'}`}>{current?.extraction_method === 'ocr' ? 'OCR text' : current?.extraction_method === 'embedded' ? 'Embedded text' : 'No extracted text'}</span></div><div className="source-note"><Check /> This panel reproduces extracted source text. Editorial metadata is labeled elsewhere.</div><article className="transcript">{current?.preferred_searchable_text || 'No usable embedded text was found on this page. It has been queued for OCR and human review.'}</article></section>
    </div>
  </div>
}

function EntityPage() {
  const { slug = '' } = useParams(); const entity = useLoad(() => api.entity(slug), [slug])
  return <PageShell eyebrow="ENTITY INDEX" title={entity.data?.name || 'Entity record'} intro={entity.data?.description || 'Mentions connect this entity to exact source pages. Automated or editorial entity matches remain labeled until reviewed.'}>{entity.loading ? <LoadingRows /> : <EmptyArchive />}</PageShell>
}

function ClaimPage() {
  const { slug = '' } = useParams(); const claim = useLoad(() => api.claims(slug), [slug])
  return <PageShell eyebrow="CLAIM RECORD" title={claim.data?.title || 'Claim record'} intro={claim.data?.normalized_claim_text || 'Claims are presented with status, evidence classification, and page-level citations. An allegation is never displayed as a confirmed fact.'}>{claim.data?.citations?.map((c: any) => <Link className="result-card" to={c.page_url} key={c.id}><span className={`claim-status ${c.relationship_type}`}>{c.relationship_type}</span><p>{c.excerpt}</p></Link>) || <EmptyArchive />}</PageShell>
}

function NotFound() { return <PageShell eyebrow="404" title="Record not found" intro="The requested archive record does not exist or has not been imported."><Link className="download-button" to="/">Return home</Link></PageShell> }

export default function App() {
  return <><ApiWakeScreen /><Layout><Routes><Route path="/" element={<HomePage />} /><Route path="/collections" element={<CollectionsIndex />} /><Route path="/collections/:slug" element={<CollectionPage />} /><Route path="/search" element={<SearchPage />} /><Route path="/documents/:id" element={<DocumentPage />} /><Route path="/documents/:id/pages/:page" element={<DocumentPage />} /><Route path="/entities/:slug" element={<EntityPage />} /><Route path="/claims/:slug" element={<ClaimPage />} /><Route path="*" element={<NotFound />} /></Routes></Layout></>
}
