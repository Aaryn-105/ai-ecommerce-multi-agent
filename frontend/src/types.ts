/** Shared TypeScript types matching backend Pydantic schemas. */

// ── Chat ────────────────────────────────────────────────

export interface ChatRequest {
  message: string;
  conversation_id?: string | null;
}

export interface ChatResponse {
  reply: string;
  conversation_id: string;
  plan: Record<string, unknown>[];
  sections: Record<string, unknown>;
}

// ── Dashboard ───────────────────────────────────────────

export interface PriceSegment {
  segment: string;
  count: number;
  min_price: number;
  max_price: number;
  avg_price: number;
}

export interface SalesTrendPoint {
  day: number;
  total_sales: number;
  total_revenue: number;
  order_count: number;
}

export interface HotRankingItem {
  id: number;
  title: string;
  category: string;
  price: number;
  rating: number;
  review_count: number;
  composite_score: number;
  image: string;
}

export interface RatingScatterPoint {
  id: number;
  title: string;
  category: string;
  price: number;
  rating: number;
  review_count: number;
  image: string;
}

export interface CategorySummary {
  category: string;
  product_count: number;
  avg_price: number;
  min_price: number;
  max_price: number;
  avg_rating: number;
  total_reviews: number;
}

export interface ProductRaw {
  id: number;
  title: string;
  price: number;
  description: string;
  category: string;
  image: string;
  rating: { rate: number; count: number };
}

// ── Report ──────────────────────────────────────────────

export interface ReportItem {
  id: number;
  title: string;
  summary: string;
  created_at: string | null;
}

export interface ReportDetail {
  id: number;
  conversation_id: number | null;
  title: string;
  summary: string | null;
  sections: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export interface ExportRequest {
  report_id: number;
  format: "pdf" | "docx";
  sections?: Record<string, unknown>;
}
