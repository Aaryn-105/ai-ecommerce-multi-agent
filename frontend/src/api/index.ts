/** Axios API client with all backend endpoint methods. */
import axios from "axios";
import type {
  ChatRequest,
  ChatResponse,
  PriceSegment,
  SalesTrendPoint,
  HotRankingItem,
  RatingScatterPoint,
  CategorySummary,
  ProductRaw,
  ReportItem,
  ReportDetail,
} from "../types";

const http = axios.create({
  baseURL: "/api/v1",
  timeout: 60000,
  headers: { "Content-Type": "application/json" },
});

// ── Chat ────────────────────────────────────────────────

export async function sendMessage(
  message: string,
  conversation_id?: string | null,
): Promise<ChatResponse> {
  const payload: ChatRequest = { message, conversation_id };
  const resp = await http.post<ChatResponse>("/chat", payload);
  return resp.data;
}

// ── Dashboard ───────────────────────────────────────────

export async function fetchProducts(): Promise<ProductRaw[]> {
  const resp = await http.get<ProductRaw[]>("/dashboard/products");
  return resp.data;
}

export async function fetchPriceDistribution(): Promise<PriceSegment[]> {
  const resp = await http.get<PriceSegment[]>("/dashboard/price-distribution");
  return resp.data;
}

export async function fetchSalesTrend(days = 30): Promise<SalesTrendPoint[]> {
  const resp = await http.get<SalesTrendPoint[]>("/dashboard/sales-trend", {
    params: { days },
  });
  return resp.data;
}

export async function fetchHotRanking(topN = 10): Promise<HotRankingItem[]> {
  const resp = await http.get<HotRankingItem[]>("/dashboard/hot-ranking", {
    params: { top_n: topN },
  });
  return resp.data;
}

export async function fetchRatingScatter(): Promise<RatingScatterPoint[]> {
  const resp = await http.get<RatingScatterPoint[]>("/dashboard/rating-scatter");
  return resp.data;
}

export async function fetchCategorySummary(): Promise<CategorySummary[]> {
  const resp = await http.get<CategorySummary[]>("/dashboard/category-summary");
  return resp.data;
}

// ── Report ──────────────────────────────────────────────

export async function listReports(
  skip = 0,
  limit = 20,
): Promise<ReportItem[]> {
  const resp = await http.get<ReportItem[]>("/report/", {
    params: { skip, limit },
  });
  return resp.data;
}

export async function getReport(id: number): Promise<ReportDetail> {
  const resp = await http.get<ReportDetail>(`/report/${id}`);
  return resp.data;
}

export async function exportReport(
  reportId: number,
  format: "pdf" | "docx",
  sections?: Record<string, unknown>,
): Promise<Blob> {
  const resp = await http.post(
    "/report/export",
    { report_id: reportId, format, sections },
    { responseType: "blob" },
  );
  return resp.data;
}

// ── Health ──────────────────────────────────────────────

export async function healthCheck(): Promise<{ status: string; version: string }> {
  const resp = await http.get<{ status: string; version: string }>("/../health");
  return resp.data;
}
