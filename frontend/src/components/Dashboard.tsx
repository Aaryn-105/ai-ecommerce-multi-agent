/**
 * Dashboard — 4-chart data visualization backed by real FakeStore API.
 */
import { useEffect, useState, useCallback } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, Legend,
  ScatterChart, Scatter, ZAxis,
} from "recharts";
import {
  fetchPriceDistribution, fetchSalesTrend, fetchHotRanking,
  fetchRatingScatter, fetchCategorySummary,
} from "../api";
import type {
  PriceSegment, SalesTrendPoint, HotRankingItem,
  RatingScatterPoint, CategorySummary,
} from "../types";

/* ── Chinese text helpers ──────────────────────────── */
const _ = (n: number) => String.fromCharCode(n);

const TXT_NODATA     = _(26242)+_(26080)+_(25968)+_(25454);   // 暂无数据
const TXT_PRICEDIST  = _(20215)+_(26684)+_(20998)+_(24067);   // 价格分布
const TXT_PRICEDESC  = _(21508)+_(20215)+_(26684)+_(26666)+_(38388)+_(30340)+_(21830)+_(21697)+_(25968)+_(37327)+_(20998)+_(24067);
const TXT_SALESTREND = _(38144)+_(37327)+_(36235)+_(21183);   // 销量趋势
const TXT_HOTRANK    = _(29190)+_(27454)+_(25490)+_(34892)+_(27036);  // 爆款排行榜
const TXT_SCATTER    = _(35780)+_(20998)+"-"+_(35780)+_(35770)+_(25968)+_(25955)+_(28857)+_(22270);
const TXT_SCATTERDESC= _(25353)+_(21697)+_(31867)+_(20998)+_(32452)+_(30340)+_(35780)+_(20998)+_(19982)+_(35780)+_(35770)+_(25968)+_(20851)+_(31995);

/* ── Shared Tooltip ─────────────────────────────────── */
interface TooltipProps {
  active?: boolean;
  payload?: Array<{ color: string; name: string; value: number }>;
  label?: string;
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

/* ── Price Distribution (BarChart) ──────────────────── */
function PriceDistributionChart({ data }: { data: PriceSegment[] }) {
  if (!data.length) return <div className="dash-chart-empty">{TXT_NODATA}</div>;
  const chartData = data.map(s => ({ name: s.segment, count: s.count }));
  return (
    <div className="dash-chart-card">
      <h3 className="dash-chart-title">{TXT_PRICEDIST}</h3>
      <p className="dash-chart-desc">{TXT_PRICEDESC}</p>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip content={<DashTooltip />} />
          <Bar dataKey="count" name="商品数量" fill="#0f3460" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ── Sales Trend (LineChart) ────────────────────────── */
function SalesTrendChart({ data }: { data: SalesTrendPoint[] }) {
  if (!data.length) return <div className="dash-chart-empty">{TXT_NODATA}</div>;
  const chartData = data.map(d => ({ day: d.day, sales: d.total_sales, revenue: Math.round(d.total_revenue) }));
  return (
    <div className="dash-chart-card">
      <h3 className="dash-chart-title">{TXT_SALESTREND}</h3>
      <p className="dash-chart-desc">近 {data.length} 天销售趋势（销量 / 收入）</p>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="day" tick={{ fontSize: 11 }} label={{ value: "天", position: "insideBottomRight", offset: -4 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip content={<DashTooltip />} />
          <Legend />
          <Line type="monotone" dataKey="sales" name="销量" stroke="#e94560" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="revenue" name="收入" stroke="#0f3460" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ── Hot Ranking (Table + Score Bar) ────────────────── */
function HotRankingTable({ data }: { data: HotRankingItem[] }) {
  if (!data.length) return <div className="dash-chart-empty">{TXT_NODATA}</div>;
  const maxScore = Math.max(...data.map(d => d.composite_score));
  return (
    <div className="dash-chart-card">
      <h3 className="dash-chart-title">{TXT_HOTRANK}</h3>
      <p className="dash-chart-desc">综合评分 Top {data.length} 商品</p>
      <div className="dash-ranking-table">
        <div className="dash-ranking-header">
          <span className="col-rank">#</span>
          <span className="col-name">商品</span>
          <span className="col-cat">品类</span>
          <span className="col-price">价格</span>
          <span className="col-rating">评分</span>
          <span className="col-score">综合分</span>
        </div>
        {data.map((item, i) => (
          <div key={item.id} className={`dash-ranking-row ${i < 3 ? "dash-top" : ""}`}>
            <span className="col-rank">
              {i === 0 ? "\u{1f947}" : i === 1 ? "\u{1f948}" : i === 2 ? "\u{1f949}" : i + 1}
            </span>
            <span className="col-name" title={item.title}>
              <img src={item.image} alt="" className="dash-rank-img" />
              <span className="dash-rank-title">
                {item.title.length > 30 ? item.title.slice(0, 30) + "..." : item.title}
              </span>
            </span>
            <span className="col-cat">{item.category}</span>
            <span className="col-price">${item.price.toFixed(2)}</span>
            <span className="col-rating">{"\u2b50"} {item.rating}</span>
            <span className="col-score">
              <div className="dash-score-bar-bg">
                <div
                  className="dash-score-bar"
                  style={{ width: `${(item.composite_score / maxScore) * 100}%` }}
                />
              </div>
              <span className="dash-score-text">{item.composite_score.toFixed(1)}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Rating Scatter (ScatterChart) ──────────────────── */
const CATEGORY_COLORS: Record<string, string> = {
  electronics: "#e94560",
  jewelery: "#f59e0b",
  "men's clothing": "#0f3460",
  "women's clothing": "#22c55e",
};

interface ScatterPoint {
  x: number;
  y: number;
  name: string;
  price: number;
}

function RatingScatterChart({ data }: { data: RatingScatterPoint[] }) {
  if (!data.length) return <div className="dash-chart-empty">{TXT_NODATA}</div>;
  const grouped: Record<string, ScatterPoint[]> = {};
  for (const p of data) {
    if (!grouped[p.category]) grouped[p.category] = [];
    grouped[p.category].push({ x: p.rating, y: p.review_count, name: p.title, price: p.price });
  }
  return (
    <div className="dash-chart-card">
      <h3 className="dash-chart-title">{TXT_SCATTER}</h3>
      <p className="dash-chart-desc">{TXT_SCATTERDESC}</p>
      <ResponsiveContainer width="100%" height={320}>
        <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="x" name="评分" domain={[0, 5]} tick={{ fontSize: 12 }}
            label={{ value: "评分", position: "insideBottomRight", offset: -4 }} />
          <YAxis dataKey="y" name="评论数" tick={{ fontSize: 11 }}
            label={{ value: "评论数", angle: -90, position: "insideLeft" }} />
          <ZAxis dataKey="price" range={[40, 300]} />
          <Tooltip content={({ active, payload }: any) => {
            if (!active || !payload?.length) return null;
            const d = payload[0].payload;
            return (
              <div className="dash-tooltip">
                <div className="dash-tooltip-label">{d.name}</div>
                <div className="dash-tooltip-row">评分: <strong>{d.x}</strong></div>
                <div className="dash-tooltip-row">评论数: <strong>{d.y}</strong></div>
                <div className="dash-tooltip-row">价格: <strong>${d.price}</strong></div>
              </div>
            );
          }} />
          <Legend />
          {Object.entries(grouped).map(([cat, points]) => (
            <Scatter key={cat} name={cat} data={points} fill={CATEGORY_COLORS[cat] || "#666"} shape="circle" />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ── Category Summary Cards ─────────────────────────── */
const CAT_ICONS: Record<string, string> = {
  electronics: "\u{1f4f1}",
  jewelery: "\u{1f48d}",
  "men's clothing": "\u{1f454}",
  "women's clothing": "\u{1f45a}",
};

function CategoryCards({ data }: { data: CategorySummary[] }) {
  if (!data.length) return null;
  return (
    <div className="dash-category-cards">
      {data.map(cat => (
        <div key={cat.category} className="dash-cat-card">
          <div className="dash-cat-icon">{CAT_ICONS[cat.category] || "\u{1f4e6}"}</div>
          <div className="dash-cat-name">{cat.category}</div>
          <div className="dash-cat-stats">
            <span>{cat.product_count} 件商品</span>
            <span>均价 ${cat.avg_price.toFixed(2)}</span>
          </div>
          <div className="dash-cat-stats">
            <span>{cat.avg_rating.toFixed(1)} 评分</span>
            <span>{cat.total_reviews} 条评论</span>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Main Dashboard ─────────────────────────────────── */
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
      setError(err instanceof Error ? err.message : "数据加载失败，请检查后端服务");
    } finally {
      setLoading(false);
    }
  }, [days, topN]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  return (
    <div className="dashboard">
      <div className="dash-header">
        <h2>数据看板</h2>
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
            排行榜 Top:
            <select value={topN} onChange={(e) => setTopN(Number(e.target.value))}>
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
            </select>
          </label>
          <button className="dash-refresh-btn" onClick={loadData} disabled={loading}>
            {loading ? "加载中..." : "\u{1f504} 刷新"}
          </button>
        </div>
      </div>

      {error && <div className="dash-error">{error}</div>}

      {loading ? (
        <div className="dash-loading">
          <div className="loading-spinner" />
          <span>正在加载数据看板...</span>
        </div>
      ) : (
        <>
          <CategoryCards data={catData} />
          <div className="dash-chart-grid">
            <PriceDistributionChart data={priceData} />
            <SalesTrendChart data={trendData} />
          </div>
          <div className="dash-chart-grid">
            <HotRankingTable data={rankingData} />
            <RatingScatterChart data={scatterData} />
          </div>
        </>
      )}
    </div>
  );
}
