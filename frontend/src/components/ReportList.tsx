import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listReports } from "../api";
import type { ReportItem } from "../types";

/* ── Chinese text helpers ───────────────────── */
const _ = (n: number): string => String.fromCharCode(n);

const TXT_TITLE   = _(21382)+_(21490)+_(25253)+_(21578);
const TXT_NODATA  = _(26242)+_(26377)+_(25253)+_(21578)+_(65292)+_(35831)+_(20808)+_(36890)+_(36807)+_(23545)+_(35805)+_(21019)+_(25104)+_(24773)+_(25104)+_(35029);
const TXT_ID      = _(32534)+_(21495);
const TXT_TITLEH  = _(25253)+_(21578)+_(26631)+_(21517);
const TXT_SUMMARY = _(25619)+_(35201);
const TXT_CREATED = _(21019)+_(25104)+_(26085)+_(26399);
const TXT_PREV    = _(19978)+_(19968)+_(39029);
const TXT_NEXT    = _(19979)+_(19968)+_(39029);
const TXT_LOADING = _(27491)+_(22312)+_(21152)+_(36733)+_(25253)+_(21578)+_(21015)+_(21333);
const TXT_ERROR   = _(21152)+_(36733)+_(22833)+_(36133);
const TXT_RETRY   = _(37325)+_(35797);

/* ── Helper: format date ────────────────────── */
function formatDate(iso: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleDateString("zh-CN", {
    year: "numeric" as const, month: "2-digit" as const, day: "2-digit" as const,
    hour: "2-digit" as const, minute: "2-digit" as const,
  });
}

/* ── Report List Page ────────────────────────── */
export default function ReportList() {
  const navigate = useNavigate();
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [skip, setSkip] = useState<number>(0);
  const [total, setTotal] = useState<number>(0);
  const limit = 20;

  const loadReports = async (currentSkip: number): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const data = await listReports(currentSkip, limit);
      setReports(data);
      setTotal(currentSkip + data.length);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadReports(skip); }, [skip]);

  const hasPrev = skip > 0;
  const hasNext = reports.length === limit;
  const currentPage = Math.floor(skip / limit) + 1;
  const totalPages = Math.ceil(total / limit) || 1;

  return (
    <div className="report-list-page">
      <div className="report-list-header">
        <h2>{TXT_TITLE}</h2>
      </div>
      {loading && (
        <div className="report-loading">
          <div className="loading-spinner" />
          <span>{TXT_LOADING}</span>
        </div>
      )}
      {error && (
        <div className="report-error">
          <p>{TXT_ERROR}: {error}</p>
          <button className="report-retry-btn" onClick={() => loadReports(skip)}>{TXT_RETRY}</button>
        </div>
      )}
      {!loading && !error && reports.length === 0 && (
        <div className="report-empty">
          <div className="report-empty-icon">{String.fromCharCode(55357, 56644)}</div>
          <p>{TXT_NODATA}</p>
        </div>
      )}
      {!loading && !error && reports.length > 0 && (
        <>
          <table className="report-table">
            <thead><tr>
              <th className="col-id">{TXT_ID}</th>
              <th className="col-title">{TXT_TITLEH}</th>
              <th className="col-summary">{TXT_SUMMARY}</th>
              <th className="col-date">{TXT_CREATED}</th>
            </tr></thead>
            <tbody>
              {reports.map((r: ReportItem) => (
                <tr key={r.id} className="report-row" onClick={() => navigate("/report/" + r.id)}>
                  <td className="col-id">{r.id}</td>
                  <td className="col-title"><span className="report-row-title">{r.title}</span></td>
                  <td className="col-summary"><span className="report-row-summary">{r.summary || "-"}</span></td>
                  <td className="col-date">{formatDate(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="report-pagination">
            <button className={"report-page-btn" + (hasPrev ? "" : " disabled")} disabled={!hasPrev} onClick={() => setSkip(skip - limit)}>
              &larr; {TXT_PREV}
            </button>
            <span className="report-page-text">{currentPage} / {totalPages}</span>
            <button className={"report-page-btn" + (hasNext ? "" : " disabled")} disabled={!hasNext} onClick={() => setSkip(skip + limit)}>
              {TXT_NEXT} &rarr;
            </button>
          </div>
        </>
      )}
    </div>
  );
}