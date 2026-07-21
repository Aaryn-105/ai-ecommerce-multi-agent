/**
 * Dashboard - 4-chart data visualization backed by real FakeStore API.
 * Redesigned with:
 *   - KPI / Category as n×2 key-value tables
 *   - Charts with explicit X/Y axis labels
 *   - Hot Ranking with product thumbnails and header labels
 */
import { useEffect, useState, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Legend,
  ScatterChart, Scatter, ZAxis, Label,
} from "recharts";
import {
  fetchPriceDistribution, fetchSalesTrend, fetchHotRanking,
  fetchRatingScatter, fetchCategorySummary,
} from "../api";
import type {
  PriceSegment, SalesTrendPoint, HotRankingItem,
  RatingScatterPoint, CategorySummary,
} from "../types";

/* ── Chinese text ─────────────────────────────────────── */
const TXT = {
  NODATA: "暂无数据",
  HEADER_TITLE: "数据看板",
  HEADER_SUB: "实时电商数据监控 · FakeStore API v2.0",
  REFRESH: "刷新",
  LOADING: "正在加载数据看板...",
  ERROR: "数据加载失败，请检查后端服务",

  /* KPI section */
  SEC_KPI: "核心指标",
  SEC_KPI_HINT: "· 关键运营数据概览",
  KPI_TOTAL:    "商品总数",
  KPI_REVENUE:  "总销售额",
  KPI_RATING:   "平均评分",
  KPI_HOT:      "爆款商品",
  KPI_TOTAL_SUB:   "活跃 SKU",
  KPI_REVENUE_SUB: "近 30 天累计",
  KPI_RATING_SUB:  "用户满意度",
  KPI_HOT_SUB:     "评分 ≥ 4.5",

  /* Category section */
  SEC_CAT: "类目概况",
  SEC_CAT_HINT: "· 4 个商品类目",
  CAT_LABEL_NAME:   "类目名称",
  CAT_LABEL_COUNT:  "商品数量",
  CAT_LABEL_PRICE:  "平均价格",
  CAT_LABEL_RATING: "平均评分",

  /* Charts section */
  SEC_CHARTS: "数据可视化",
  CHART_PRICE:    "价格分布",
  CHART_PRICE_DESC: "按价格区间统计商品数量",
  CHART_PRICE_BADGE: "5 个价格带",
  CHART_PRICE_X: "价格区间",
  CHART_PRICE_Y: "商品数量",

  CHART_TREND:    "销量趋势",
  CHART_TREND_DESC: "近 30 天销售趋势（销量 / 收入）",
  CHART_TREND_BADGE: "实时",
  CHART_TREND_X: "天数",
  CHART_TREND_Y_LEFT: "销量（件）",
  CHART_TREND_Y_RIGHT: "收入（$）",

  CHART_HOT:      "爆款排行榜",
  CHART_HOT_DESC: "按综合评分排序的 Top 10 商品",
  CHART_HOT_BADGE: "Top 10",
  HOT_COL_RANK:    "排名",
  HOT_COL_PRODUCT: "商品",
  HOT_COL_CAT:     "类目",
  HOT_COL_PRICE:   "价格",
  HOT_COL_RATING:  "评分",
  HOT_COL_REVIEWS: "评论数",
  HOT_COL_SCORE:   "综合分",

  CHART_SCATTER:  "评分分布",
  CHART_SCATTER_DESC: "各商品评分-评论数关系（按类目着色）",
  CHART_SCATTER_BADGE: "散点图",
  CHART_SCATTER_X: "商品评分",
  CHART_SCATTER_Y: "评论数",
};

/* ── Shared Tooltip ───────────────────────────────────── */
interface TooltipProps {
  active?: boolean;
  payload?: Array<{ color: string; name: string; value: number }>;
  label?: string | number;
}

function DashTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="dash-tooltip">
      <div className="dash-tooltip-label">{label}</div>
      {payload.map((entry, i) => (
        <div key={i} className="dash-tooltip-row">
          <span style={{ color: entry.color }}>{entry.name}: </span>
          <strong>
            {typeof entry.value === "number" ? entry.value.toLocaleString() : entry.value}
          </strong>
        </div>
      ))}
    </div>
  );
}

/* ── Section Title ────────────────────────────────────── */
function SectionTitle({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="dash-section-title">
      <div className="dash-section-bar" />
      <h3>{title}</h3>
      {hint && <span className="dash-section-hint">{hint}</span>}
    </div>
  );
}

/* ── KPI Section (n×2 table) ──────────────────────────── */
interface KPIRow {
  icon: string;
  iconColor: string;
  label: string;
  value: string;
  unit: string;
  trend: string;
  trendUp: boolean;
  sub: string;
}

function KPITable({ summary }: { summary: { total: number; revenue: number; avgRating: number; hotCount: number } }) {
  const rows: KPIRow[] = [
    {
      icon: "📦", iconColor: "primary",
      label: TXT.KPI_TOTAL,
      value: String(summary.total),
      unit: "件",
      trend: "+12%", trendUp: true,
      sub: TXT.KPI_TOTAL_SUB,
    },
    {
      icon: "💰", iconColor: "success",
      label: TXT.KPI_REVENUE,
      value: summary.revenue.toLocaleString(),
      unit: "$",
      trend: "+8.5%", trendUp: true,
      sub: TXT.KPI_REVENUE_SUB,
    },
    {
      icon: "⭐", iconColor: "warning",
      label: TXT.KPI_RATING,
      value: summary.avgRating.toFixed(1),
      unit: "/ 5",
      trend: "+0.2", trendUp: true,
      sub: TXT.KPI_RATING_SUB,
    },
    {
      icon: "🔥", iconColor: "accent",
      label: TXT.KPI_HOT,
      value: String(summary.hotCount),
      unit: "款",
      trend: "+3", trendUp: true,
      sub: TXT.KPI_HOT_SUB,
    },
  ];
  return (
    <div className="dash-table">
      <div className="dash-table-head">
        <div className="dash-table-th dash-col-label">指标</div>
        <div className="dash-table-th dash-col-value">数值</div>
      </div>
      <div className="dash-table-body">
        {rows.map((r) => (
          <div key={r.label} className="dash-table-row">
            <div className="dash-table-td dash-col-label">
              <div className={"dash-kpi-icon " + r.iconColor}>{r.icon}</div>
              <div className="dash-kpi-label-block">
                <span className="dash-kpi-label">{r.label}</span>
                <span className="dash-kpi-sub">{r.sub}</span>
              </div>
            </div>
            <div className="dash-table-td dash-col-value">
              <div className="dash-kpi-value-num">{r.value}</div>
              <div className="dash-kpi-value-unit">{r.unit}</div>
              <div className={"dash-kpi-trend " + (r.trendUp ? "up" : "down")}>
                <span>{r.trendUp ? "↑" : "↓"}</span>
                <span>{r.trend}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Category Table (n×2) ──────────────────────────────── */
const CAT_ICONS: Record<string, string> = {
  electronics: "📱",
  jewelery: "💎",
  "men's clothing": "👔",
  "women's clothing": "👗",
};

const CAT_COLORS: Record<string, string> = {
  electronics: "primary",
  jewelery: "accent",
  "men's clothing": "success",
  "women's clothing": "warning",
};

function CategoryTable({ data }: { data: CategorySummary[] }) {
  if (!data.length) return <div className="dash-chart-empty">{TXT.NODATA}</div>;
  return (
    <div className="dash-table">
      <div className="dash-table-head">
        <div className="dash-table-th dash-col-cat-name">类目</div>
        <div className="dash-table-th dash-col-cat-count">{TXT.CAT_LABEL_COUNT}</div>
        <div className="dash-table-th dash-col-cat-price">{TXT.CAT_LABEL_PRICE}</div>
        <div className="dash-table-th dash-col-cat-rating">{TXT.CAT_LABEL_RATING}</div>
      </div>
      <div className="dash-table-body">
        {data.map((cat) => (
          <div key={cat.category} className="dash-table-row">
            <div className="dash-table-td dash-col-cat-name">
              <div className={"dash-cat-icon " + (CAT_COLORS[cat.category] || "primary")}>
                {CAT_ICONS[cat.category] || "📦"}
              </div>
              <div className="dash-cat-name-block">
                <span className="dash-cat-name">{cat.category}</span>
                <span className="dash-cat-sub">{CAT_ICONS[cat.category] ? "" : ""}</span>
              </div>
            </div>
            <div className="dash-table-td dash-col-cat-count">
              <span className="dash-cat-value">{cat.product_count}</span>
              <span className="dash-cat-unit">件</span>
            </div>
            <div className="dash-table-td dash-col-cat-price">
              <span className="dash-cat-symbol">$</span>
              <span className="dash-cat-value">{cat.avg_price.toFixed(2)}</span>
            </div>
            <div className="dash-table-td dash-col-cat-rating">
              <span className="dash-cat-value dash-rating">{cat.avg_rating.toFixed(1)}</span>
              <span className="dash-cat-unit">/ 5</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Price Distribution (BarChart) ─────────────────────── */
function PriceDistributionChart({ data }: { data: PriceSegment[] }) {
  if (!data.length) return <div className="dash-chart-empty">{TXT.NODATA}</div>;
  const chartData = data.map(s => ({ name: s.segment, count: s.count }));
  return (
    <div className="dash-chart-card">
      <div className="dash-chart-header">
        <div className="dash-chart-titles">
          <h3 className="dash-chart-title">{TXT.CHART_PRICE}</h3>
          <p className="dash-chart-desc">{TXT.CHART_PRICE_DESC}</p>
        </div>
        <span className="dash-chart-badge primary">{TXT.CHART_PRICE_BADGE}</span>
      </div>
      <div className="dash-chart-area">
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData} margin={{ top: 24, right: 24, left: 16, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              axisLine={{ stroke: "#cbd5e1" }}
              tickLine={false}
            >
              <Label value={TXT.CHART_PRICE_X} offset={-18} position="insideBottom" fontSize={12} fill="#475569" fontWeight={600} />
            </XAxis>
            <YAxis
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              axisLine={false}
              tickLine={false}
              allowDecimals={false}
            >
              <Label value={TXT.CHART_PRICE_Y} angle={-90} position="insideLeft" fontSize={12} fill="#475569" fontWeight={600} style={{ textAnchor: "middle" }} />
            </YAxis>
            <Tooltip content={<DashTooltip />} cursor={{ fill: "rgba(15,52,96,0.06)" }} />
            <Bar dataKey="count" name="商品数量" fill="#0f3460" radius={[6, 6, 0, 0]} maxBarSize={48} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/* ── Sales Trend (LineChart) ───────────────────────────── */
function SalesTrendChart({ data }: { data: SalesTrendPoint[] }) {
  if (!data.length) return <div className="dash-chart-empty">{TXT.NODATA}</div>;
  const chartData = data.map(d => ({
    day: d.day,
    sales: d.total_sales,
    revenue: Math.round(d.total_revenue),
  }));
  return (
    <div className="dash-chart-card">
      <div className="dash-chart-header">
        <div className="dash-chart-titles">
          <h3 className="dash-chart-title">{TXT.CHART_TREND}</h3>
          <p className="dash-chart-desc">{TXT.CHART_TREND_DESC}</p>
        </div>
        <span className="dash-chart-badge accent">{TXT.CHART_TREND_BADGE}</span>
      </div>
      <div className="dash-chart-area">
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chartData} margin={{ top: 24, right: 24, left: 16, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
            <XAxis
              dataKey="day"
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              axisLine={{ stroke: "#cbd5e1" }}
              tickLine={false}
            >
              <Label value={TXT.CHART_TREND_X} offset={-18} position="insideBottom" fontSize={12} fill="#475569" fontWeight={600} />
            </XAxis>
            <YAxis
              yAxisId="left"
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              axisLine={{ stroke: "#e94560" }}
              tickLine={false}
            >
              <Label value={TXT.CHART_TREND_Y_LEFT} angle={-90} position="insideLeft" fontSize={12} fill="#475569" fontWeight={600} style={{ textAnchor: "middle" }} />
            </YAxis>
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              axisLine={{ stroke: "#0f3460" }}
              tickLine={false}
            >
              <Label value={TXT.CHART_TREND_Y_RIGHT} angle={90} position="insideRight" fontSize={12} fill="#475569" fontWeight={600} style={{ textAnchor: "middle" }} />
            </YAxis>
            <Tooltip content={<DashTooltip />} />
            <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
            <Line yAxisId="left"  type="monotone" dataKey="sales"   name="销量"    stroke="#e94560" strokeWidth={2.5} dot={false} activeDot={{ r: 5 }} />
            <Line yAxisId="right" type="monotone" dataKey="revenue" name="收入 ($)" stroke="#0f3460" strokeWidth={2.5} dot={false} activeDot={{ r: 5 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/* ── Hot Ranking Table (with images + header labels) ───── */
function HotRankingTable({ data }: { data: HotRankingItem[] }) {
  if (!data.length) return <div className="dash-chart-empty">{TXT.NODATA}</div>;
  const maxScore = Math.max(...data.map(d => d.composite_score));
  const minScore = Math.min(...data.map(d => d.composite_score));
  const range = Math.max(maxScore - minScore, 1);

  function barLevel(score: number): "high" | "mid" | "low" {
    const normalized = (score - minScore) / range;
    if (normalized >= 0.66) return "high";
    if (normalized >= 0.33) return "mid";
    return "low";
  }

  return (
    <div className="dash-chart-card dash-hot-card">
      <div className="dash-chart-header">
        <div className="dash-chart-titles">
          <h3 className="dash-chart-title">{TXT.CHART_HOT}</h3>
          <p className="dash-chart-desc">{TXT.CHART_HOT_DESC}</p>
        </div>
        <span className="dash-chart-badge accent">{TXT.CHART_HOT_BADGE}</span>
      </div>

      {/* Column header row - left-side labels indicating data meaning */}
      <div className="dash-hot-header-row">
        <div className="dash-hot-th">{TXT.HOT_COL_RANK}</div>
        <div className="dash-hot-th dash-hot-th-product">{TXT.HOT_COL_PRODUCT}</div>
        <div className="dash-hot-th">{TXT.HOT_COL_CAT}</div>
        <div className="dash-hot-th">{TXT.HOT_COL_PRICE}</div>
        <div className="dash-hot-th">{TXT.HOT_COL_RATING}</div>
        <div className="dash-hot-th">{TXT.HOT_COL_REVIEWS}</div>
        <div className="dash-hot-th dash-hot-th-score">{TXT.HOT_COL_SCORE}</div>
      </div>

      <div className="dash-hot-list">
        {data.map((r) => {
          const fillPct = Math.max(8, Math.min(100, ((r.composite_score - minScore) / range) * 100 + 15));
          const lvl = barLevel(r.composite_score);
          const rankClass = r.id === 1 ? "top-1" : r.id === 2 ? "top-2" : r.id === 3 ? "top-3" : "";
          return (
            <div key={r.id} className="dash-hot-row">
              {/* Rank */}
              <div className="dash-hot-td dash-hot-td-rank">
                <div className={"dash-hot-rank " + rankClass}>{r.id}</div>
              </div>

              {/* Product (with thumbnail) */}
              <div className="dash-hot-td dash-hot-td-product">
                <img
                  className="dash-hot-thumb"
                  src={r.image}
                  alt={r.title}
                  loading="lazy"
                  onError={(e) => {
                    const t = e.currentTarget;
                    t.style.display = "none";
                    const fb = t.nextElementSibling as HTMLElement | null;
                    if (fb) fb.style.display = "flex";
                  }}
                />
                <div className="dash-hot-thumb-fallback" style={{ display: "none" }}>📦</div>
                <div className="dash-hot-title">{r.title}</div>
              </div>

              {/* Category */}
              <div className="dash-hot-td dash-hot-td-cat">
                <span className="dash-hot-cat-pill">{r.category}</span>
              </div>

              {/* Price */}
              <div className="dash-hot-td dash-hot-td-price">
                <span className="dash-hot-price-symbol">$</span>
                <span className="dash-hot-price-num">{r.price}</span>
              </div>

              {/* Rating */}
              <div className="dash-hot-td dash-hot-td-rating">
                <span className="dash-hot-rating-star">⭐</span>
                <span className="dash-hot-rating-num">{r.rating}</span>
              </div>

              {/* Reviews */}
              <div className="dash-hot-td dash-hot-td-reviews">
                <span className="dash-hot-reviews-num">{r.review_count}</span>
              </div>

              {/* Score (bar + number) */}
              <div className="dash-hot-td dash-hot-td-score">
                <div className="dash-hot-bar">
                  <div className={"dash-hot-bar-fill " + lvl} style={{ width: fillPct + "%" }} />
                </div>
                <div className="dash-hot-score">{r.composite_score.toFixed(1)}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Rating Scatter ────────────────────────────────────── */
const CATEGORY_COLORS: Record<string, string> = {
  electronics: "#0f3460",
  jewelery: "#e94560",
  "men's clothing": "#22c55e",
  "women's clothing": "#f59e0b",
};

function RatingScatterChart({ data }: { data: RatingScatterPoint[] }) {
  if (!data.length) return <div className="dash-chart-empty">{TXT.NODATA}</div>;
  const grouped: Record<string, RatingScatterPoint[]> = {};
  for (const p of data) {
    if (!grouped[p.category]) grouped[p.category] = [];
    grouped[p.category].push(p);
  }
  return (
    <div className="dash-chart-card">
      <div className="dash-chart-header">
        <div className="dash-chart-titles">
          <h3 className="dash-chart-title">{TXT.CHART_SCATTER}</h3>
          <p className="dash-chart-desc">{TXT.CHART_SCATTER_DESC}</p>
        </div>
        <span className="dash-chart-badge success">{TXT.CHART_SCATTER_BADGE}</span>
      </div>
      <div className="dash-chart-area">
        <ResponsiveContainer width="100%" height={300}>
          <ScatterChart margin={{ top: 24, right: 24, left: 16, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
            <XAxis
              type="number"
              dataKey="x"
              name="评分"
              domain={[0, 5]}
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              axisLine={{ stroke: "#cbd5e1" }}
              tickLine={false}
            >
              <Label value={TXT.CHART_SCATTER_X} offset={-18} position="insideBottom" fontSize={12} fill="#475569" fontWeight={600} />
            </XAxis>
            <YAxis
              type="number"
              dataKey="y"
              name="评论数"
              tick={{ fontSize: 11, fill: "#94a3b8" }}
              axisLine={{ stroke: "#cbd5e1" }}
              tickLine={false}
            >
              <Label value={TXT.CHART_SCATTER_Y} angle={-90} position="insideLeft" fontSize={12} fill="#475569" fontWeight={600} style={{ textAnchor: "middle" }} />
            </YAxis>
            <ZAxis type="number" range={[60, 200]} />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload as { name: string; x: number; y: number; price: number };
                return (
                  <div className="dash-tooltip">
                    <div className="dash-tooltip-label">{d.name}</div>
                    <div className="dash-tooltip-row">评分: <strong>{d.x}</strong></div>
                    <div className="dash-tooltip-row">评论数: <strong>{d.y}</strong></div>
                    <div className="dash-tooltip-row">价格: <strong></strong></div>
                  </div>
                );
              }}
            />
            <Legend iconType="circle" wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
            {Object.entries(grouped).map(([cat, points]) => (
              <Scatter
                key={cat}
                name={cat}
                data={points.map(p => ({ x: p.rating, y: p.review_count, name: p.title, price: p.price }))}
                fill={CATEGORY_COLORS[cat] || "#666"}
                shape="circle"
                fillOpacity={0.78}
              />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/* ── Main Dashboard ────────────────────────────────────── */
export default function Dashboard() {
  const [priceData, setPriceData] = useState<PriceSegment[]>([]);
  const [trendData, setTrendData] = useState<SalesTrendPoint[]>([]);
  const [rankingData, setRankingData] = useState<HotRankingItem[]>([]);
  const [scatterData, setScatterData] = useState<RatingScatterPoint[]>([]);
  const [catData, setCatData] = useState<CategorySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [topN, setTopN] = useState(10);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [price, trend, ranking, scatter, cats] = await Promise.all([
        fetchPriceDistribution(),
        fetchSalesTrend(days),
        fetchHotRanking(topN),
        fetchRatingScatter(),
        fetchCategorySummary(),
      ]);
      setPriceData(price);
      setTrendData(trend);
      setRankingData(ranking);
      setScatterData(scatter);
      setCatData(cats);
    } catch (err) {
      setError(err instanceof Error ? err.message : TXT.ERROR);
    } finally {
      setLoading(false);
    }
  }, [days, topN]);

  useEffect(() => { loadData(); }, [loadData]);

  const totalProducts = catData.reduce((s, c) => s + c.product_count, 0);
  const totalRevenue = trendData.reduce((s, d) => s + d.total_revenue, 0);
  const avgRating =
    catData.length > 0
      ? catData.reduce((s, c) => s + c.avg_rating * c.product_count, 0) / Math.max(totalProducts, 1)
      : 0;
  const hotCount = rankingData.filter(r => r.rating >= 4.5).length;

  return (
    <div className="dashboard">
      {/* ── Header ── */}
      <div className="dash-header">
        <div className="dash-header-left">
          <h2>{TXT.HEADER_TITLE}</h2>
          <span className="dash-header-subtitle">{TXT.HEADER_SUB}</span>
        </div>
        <div className="dash-controls">
          <label className="dash-control">
            趋势天数:
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
              <option value={7}>7 天</option>
              <option value={30}>30 天</option>
              <option value={90}>90 天</option>
            </select>
          </label>
          <label className="dash-control">
            排行榜:
            <select value={topN} onChange={(e) => setTopN(Number(e.target.value))}>
              <option value={5}>Top 5</option>
              <option value={10}>Top 10</option>
              <option value={20}>Top 20</option>
            </select>
          </label>
          <button className="dash-refresh-btn" onClick={loadData} disabled={loading}>
            {loading ? "加载中…" : "🔄 " + TXT.REFRESH}
          </button>
        </div>
      </div>

      {error && <div className="dash-error">{error}</div>}

      {loading ? (
        <div className="dash-loading">
          <div className="loading-spinner" />
          <span>{TXT.LOADING}</span>
        </div>
      ) : (
        <>
          {/* ── Section 1: KPI Table ── */}
          <div className="dash-section">
            <SectionTitle title={TXT.SEC_KPI} hint={TXT.SEC_KPI_HINT} />
            <KPITable summary={{ total: totalProducts, revenue: Math.round(totalRevenue), avgRating, hotCount }} />
          </div>

          {/* ── Section 2: Category Table ── */}
          <div className="dash-section">
            <SectionTitle title={TXT.SEC_CAT} hint={TXT.SEC_CAT_HINT} />
            <CategoryTable data={catData} />
          </div>

          {/* ── Section 3: Charts ── */}
          <div className="dash-section">
            <SectionTitle title={TXT.SEC_CHARTS} />
            <div className="dash-chart-grid">
              <PriceDistributionChart data={priceData} />
              <SalesTrendChart data={trendData} />
            </div>
            <div className="dash-chart-grid">
              <HotRankingTable data={rankingData} />
              <RatingScatterChart data={scatterData} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}