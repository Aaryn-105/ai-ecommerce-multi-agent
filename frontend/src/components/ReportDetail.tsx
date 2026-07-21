import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { getReport, exportReport } from "../api";
import type { ReportDetail as ReportDetailType } from "../types";

/* ── Chinese text helpers ───────────────────── */
const _ = (n: number): string => String.fromCharCode(n);

const TXT_BACK = _(36820)+_(22238)+_(21040)+_(21015)+_(21333);
const TXT_LOADING = _(27491)+_(22312)+_(21152)+_(36733)+_(25253)+_(21578)+_(21333);
const TXT_RETRY = _(37325)+_(35797);
const TXT_NOTFOUND = _(25253)+_(21578)+_(19981)+_(23384)+_(22312);
const TXT_SUMMARY = _(25619)+_(35201);
const TXT_CREATED = _(21019)+_(25104)+_(26085)+_(26399);
const TXT_UPDATED = _(26356)+_(26032)+_(26085)+_(26399);
const TXT_SECTIONS = _(20998)+_(26512)+_(20869)+_(26524);
const TXT_EXPORT_PDF = _(23548)+_(20986)+String.fromCharCode(32)+_(80)+_(68)+_(70);
const TXT_EXPORT_DOCX = _(23548)+_(20986)+String.fromCharCode(32)+_(68)+_(79)+_(67)+_(88);
const TXT_EXPORTING = _(27491)+_(22312)+_(23548)+_(20986)+_(8230);
const TXT_UNKNOWN = _(26410)+_(30693);

/* ── Helper: format date ────────────────────── */
function fmtDate(iso: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleDateString("zh-CN", {
    year: "numeric" as const, month: "2-digit" as const, day: "2-digit" as const,
    hour: "2-digit" as const, minute: "2-digit" as const,
  });
}

/* ── Report Detail Page ──────────────────────── */
export default function ReportDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<ReportDetailType | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);

  const loadReport = async (): Promise<void> => {
    setLoading(true); setError(null);
    try {
      const data = await getReport(Number(id));
      setReport(data);
    } catch (err: unknown) {
      if (err && typeof err === "object" && "response" in err) {
        const axiosErr = err as { response?: { status?: number } };
        if (axiosErr.response?.status === 404) {
          setError(TXT_NOTFOUND);
        } else {
          setError(err instanceof Error ? err.message : String(err));
        }
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally { setLoading(false); }
  };
  useEffect(() => { loadReport(); }, [id]);

  const handleExport = async (format: "pdf" | "docx"): Promise<void> => {
    if (!report) return;
    setExporting(format);
    try {
      const blob = await exportReport(report.id, format, report.sections || {});
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "report_" + report.id + "." + format;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      alert("Export " + format.toUpperCase() + ": " + (err instanceof Error ? err.message : String(err)));
    } finally { setExporting(null); }
  };

  function renderSections(sections: Record<string, unknown> | null | undefined) {
    if (!sections || Object.keys(sections).length === 0)
      return <p className="report-detail-empty">{_(26242)+_(25968)+_(25454)}</p>;
    return Object.entries(sections).map(([key, val]) => {
      let c = "";
      if (typeof val === "string") c = val;
      else if (typeof val === "object" && val !== null) {
        try { c = JSON.stringify(val, null, 2); } catch { c = String(val); }
      } else c = String(val);
      return (<div key={key} className="report-section-card">
        <h4 className="report-section-title">{key}</h4>
        <pre className="report-section-content">{c}</pre>
      </div>);
    });
  }

  if (loading) return (<div className="report-loading"><div className="loading-spinner" /><span>{TXT_LOADING}</span></div>);
  if (error) return (<div className="report-error"><p>{error}</p><button className="report-retry-btn" onClick={loadReport}>{TXT_RETRY}</button><button className="report-back-btn" onClick={() => navigate("/reports")}>{TXT_BACK}</button></div>);
  if (!report) return (<div className="report-error"><p>{TXT_NOTFOUND}</p><button className="report-back-btn" onClick={() => navigate("/reports")}>{TXT_BACK}</button></div>);

  return (
    <div className="report-detail-page">
      <div className="report-detail-header">
        <button className="report-back-btn" onClick={() => navigate("/reports")}>&larr; {TXT_BACK}</button>
        <h2>{report.title || TXT_UNKNOWN}</h2>
      </div>
      <div className="report-detail-meta">
        <div className="report-meta-row"><span className="report-meta-label">{TXT_CREATED}:</span><span>{fmtDate(report.created_at)}</span></div>
        <div className="report-meta-row"><span className="report-meta-label">{TXT_UPDATED}:</span><span>{fmtDate(report.updated_at)}</span></div>
      </div>
      {report.summary && (<div className="report-detail-summary"><h3>{TXT_SUMMARY}</h3><p>{report.summary}</p></div>)}
      <div className="report-detail-actions">
        <button className="report-export-btn pdf" onClick={() => handleExport("pdf")} disabled={exporting !== null}>{exporting === "pdf" ? TXT_EXPORTING : TXT_EXPORT_PDF}</button>
        <button className="report-export-btn docx" onClick={() => handleExport("docx")} disabled={exporting !== null}>{exporting === "docx" ? TXT_EXPORTING : TXT_EXPORT_DOCX}</button>
      </div>
      <div className="report-detail-sections">
        <h3>{TXT_SECTIONS}</h3>
        {report.content ? (
          <article className="report-markdown-content">
            <ReactMarkdown>{report.content}</ReactMarkdown>
          </article>
        ) : renderSections(report.sections)}
      </div>
    </div>
  );
}
