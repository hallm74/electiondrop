export type Collection = {
  id: number; slug: string; code: string; title: string; description: string;
  source_url: string; display_order: number; document_count: number; page_count: number;
}

export type Document = {
  id: number; stable_id: string; title: string; title_source: string; collection: Collection;
  source_file: number; source_filename: string; source_sha256: string; document_type: string;
  originating_agency: string; agency_source: string; document_date: string | null;
  date_precision: string; date_source: string; summary: string; summary_source: string;
  printed_identifiers: string[]; classification_markings: string[]; declassification_markings: string[];
  start_page: number; end_page: number; page_count: number; review_state: string; has_redactions: boolean;
}

export type Page = {
  id: number; document: number; document_stable_id: string; source_file: number; source_page_number: number;
  logical_page_number: number; stable_page_id: string; extracted_text: string; ocr_text: string;
  preferred_searchable_text: string; image_url: string; printed_page_label: string;
  extraction_method: string; extraction_confidence: number; review_state: string;
}

export type SearchResult = {
  document_id: string; document_title: string; collection_slug: string; collection_title: string;
  page_number: number; stable_page_id: string; excerpt: string; agency: string; document_type: string;
  document_date: string | null; extraction_method: string; reviewed: boolean; page_url: string;
}

export type Topic = {
  slug: string; label: string; document_count: number; mention_count: number;
}

export type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] }
