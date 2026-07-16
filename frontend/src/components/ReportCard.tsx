/** ReportCard — displays a structured agent output section. */
import { useMemo } from "react";

interface ReportCardProps {
  agentName: string;
  data: Record<string, unknown>;
}

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number") return value.toLocaleString();
  if (typeof value === "boolean") return value ? "是" : "否";
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === "object" && item !== null) {
          const obj = item as Record<string, unknown>;
          return Object.values(obj).filter((v) => typeof v !== "object").join(" | ");
        }
        return String(item);
      })
      .join("\n");
  }
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    return Object.entries(obj)
      .map(([k, v]) => `${k}: ${renderValue(v)}`)
      .join("\n");
  }
  return String(value);
}

const AGENT_LABELS: Record<string, string> = {
  product_analysis: "选品分析",
  trend_forecast: "趋势预测",
  competitor_analysis: "竞品对比",
  marketing_copy: "营销文案",
  inventory_advice: "库存补货",
  pricing: "定价建议",
  campaign_planning: "促销方案",
};

const AGENT_ICONS: Record<string, string> = {
  product_analysis: "\U0001f50d",
  trend_forecast: "\U0001f4c8",
  competitor_analysis: "\u2694\ufe0f",
  marketing_copy: "\u270d\ufe0f",
  inventory_advice: "\U0001f4e6",
  pricing: "\U0001f4b0",
  campaign_planning: "\U0001f3af",
};

export default function ReportCard({ agentName, data }: ReportCardProps) {
  const label = AGENT_LABELS[agentName] ?? agentName;
  const icon = AGENT_ICONS[agentName] ?? "\U0001f4cb";

  const cardFields = useMemo(() => {
    const fields: { label: string; value: string }[] = [];

    if (data.summary) fields.push({ label: "摘要", value: String(data.summary) });
    if (data.market_summary) fields.push({ label: "市场概览", value: String(data.market_summary) });
    if (data.competitive_insight) fields.push({ label: "竞争洞察", value: String(data.competitive_insight) });

    if (Array.isArray(data.top_products) && data.top_products.length > 0) {
      const rows = (data.top_products as Record<string, unknown>[])
        .slice(0, 5)
        .map((p) => `${p.title ?? p.name ?? "—"} (评分: ${p.score ?? p.composite_score ?? "—"})`);
      fields.push({ label: "推荐商品", value: rows.join("\n") });
    }

    if (Array.isArray(data.campaigns) && data.campaigns.length > 0) {
      const rows = (data.campaigns as Record<string, unknown>[])
        .slice(0, 3)
        .map((c) => `${c.name ?? c.type ?? "方案"} — ROI: ${c.roi ?? c.expected_roi ?? "—"}`);
      fields.push({ label: "促销方案", value: rows.join("\n") });
    }

    if (data.pricing_strategy) fields.push({ label: "定价策略", value: String(data.pricing_strategy) });
    if (data.recommended_price !== undefined) fields.push({ label: "建议价格", value: String(data.recommended_price) });
    if (data.forecast_7day !== undefined) fields.push({ label: "7日预测销量", value: String(data.forecast_7day) });
    if (data.forecast_30day !== undefined) fields.push({ label: "30日预测销量", value: String(data.forecast_30day) });

    if (data.copy_sets && Array.isArray(data.copy_sets)) {
      const copyTexts = (data.copy_sets as Record<string, unknown>[])
        .slice(0, 3)
        .map((c) => c.copy ?? c.text ?? "");
      fields.push({ label: "营销文案", value: copyTexts.join("\n\n---\n\n") });
    }

    if (data.stock_level !== undefined) fields.push({ label: "库存水平", value: String(data.stock_level) });
    if (data.reorder_quantity !== undefined) fields.push({ label: "建议补货量", value: String(data.reorder_quantity) });

    return fields;
  }, [data]);

  return (
    <div className="report-card">
      <div className="report-card-header">
        <span className="report-card-icon">{icon}</span>
        <span className="report-card-title">{label}</span>
      </div>
      <div className="report-card-body">
        {cardFields.length > 0 ? (
          cardFields.map((f, i) => (
            <div key={i} className="report-card-field">
              <span className="report-card-field-label">{f.label}</span>
              <span className="report-card-field-value">{f.value}</span>
            </div>
          ))
        ) : (
          <pre className="report-card-raw">{renderValue(data)}</pre>
        )}
      </div>
    </div>
  );
}
