import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listReports, deleteReport, batchDeleteReports } from "../api";
import type { ReportItem } from "../types";

/* ── Chinese text helpers ───────────────────── */
const TXT_TITLE     = "历史报告";
const TXT_NODATA    = "暂无历史报告，快来发起一次对话分析吧";
const TXT_ID        = "ID";
const TXT_TITLEH    = "报告标题";
const TXT_SUMMARY   = "摘要";
const TXT_CREATED   = "创建时间";
const TXT_ACTIONS   = "操作";
const TXT_DEL       = "删除";
const TXT_BATCH_DEL = "批量删除";
const TXT_SELECT_ALL = "全选";
const TXT_CANCEL    = "取消";
const TXT_CONFIRM_DEL_SINGLE = "确认删除该报告？此操作不可撤销。";
const TXT_CONFIRM_DEL_BATCH  = "确认删除选中的 {n} 份报告？此操作不可撤销。";
const TXT_DEL_OK    = "删除成功";
const TXT_DEL_ERR   = "删除失败：";
const TXT_LOADING   = "正在加载报告列表…";
const TXT_ERROR     = "加载失败";
const TXT_RETRY     = "重试";
const TXT_PREV      = "上一页";
const TXT_NEXT      = "下一页";

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
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [deleteTarget, setDeleteTarget] = useState<ReportItem | null>(null);
  const [batchDeleting, setBatchDeleting] = useState<boolean>(false);
  const [deleting, setDeleting] = useState<boolean>(false);

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

  // ── Selection logic ────────────────────────────
  const allSelected = reports.length > 0 && reports.every((r) => selectedIds.has(r.id));

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(reports.map((r) => r.id)));
    }
  };

  const clearSelection = () => setSelectedIds(new Set());

  // ── Single delete ──────────────────────────────
  const confirmDelete = async (): Promise<void> => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteReport(deleteTarget.id);
      setDeleteTarget(null);
      await loadReports(skip);
      alert(TXT_DEL_OK);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(TXT_DEL_ERR + msg);
    } finally {
      setDeleting(false);
    }
  };

  // ── Batch delete ───────────────────────────────
  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return;
    setBatchDeleting(true);
    try {
      await batchDeleteReports(Array.from(selectedIds));
      setSelectedIds(new Set());
      await loadReports(skip);
      alert(TXT_DEL_OK);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      alert(TXT_DEL_ERR + msg);
    } finally {
      setBatchDeleting(false);
    }
  };

  const hasPrev = skip > 0;
  const hasNext = reports.length === limit;
  const currentPage = Math.floor(skip / limit) + 1;
  const totalPages = Math.ceil(total / limit) || 1;

  return (
    <div className="report-list-page">
      <div className="report-list-header">
        <h2>{TXT_TITLE}</h2>
        {selectedIds.size > 0 && (
          <button
            className="batch-delete-btn"
            onClick={handleBatchDelete}
            disabled={batchDeleting}
          >
            {batchDeleting ? "…" : `${TXT_BATCH_DEL} (${selectedIds.size})`}
          </button>
        )}
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
              <th className="col-check">
                <input
                  type="checkbox"
                  className="report-checkbox"
                  checked={allSelected}
                  onChange={toggleSelectAll}
                  title={TXT_SELECT_ALL}
                />
              </th>
              <th className="col-id">{TXT_ID}</th>
              <th className="col-title">{TXT_TITLEH}</th>
              <th className="col-summary">{TXT_SUMMARY}</th>
              <th className="col-date">{TXT_CREATED}</th>
              <th className="col-actions">{TXT_ACTIONS}</th>
            </tr></thead>
            <tbody>
              {reports.map((r: ReportItem) => (
                <tr
                  key={r.id}
                  className={"report-row" + (selectedIds.has(r.id) ? " selected" : "")}
                  onClick={() => navigate("/report/" + r.id)}
                >
                  <td className="col-check" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      className="report-checkbox"
                      checked={selectedIds.has(r.id)}
                      onChange={() => toggleSelect(r.id)}
                    />
                  </td>
                  <td className="col-id">{r.id}</td>
                  <td className="col-title"><span className="report-row-title">{r.title}</span></td>
                  <td className="col-summary"><span className="report-row-summary">{r.summary || "-"}</span></td>
                  <td className="col-date">{formatDate(r.created_at)}</td>
                  <td className="col-actions">
                    <button
                      type="button"
                      className="report-row-delete-btn"
                      onClick={(e) => { e.stopPropagation(); setDeleteTarget(r); }}
                      title={TXT_DEL}
                    >
                      {TXT_DEL}
                    </button>
                  </td>
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

      {/* ── Single delete confirm modal ── */}
      {deleteTarget && (
        <div className="modal-overlay" onClick={() => !deleting && setDeleteTarget(null)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <h3 className="modal-title">{TXT_CONFIRM_DEL_SINGLE}</h3>
            <p className="modal-body">
              <strong>{deleteTarget.title}</strong>
            </p>
            <div className="modal-actions">
              <button type="button" className="modal-btn modal-btn-cancel" onClick={() => setDeleteTarget(null)} disabled={deleting}>
                {TXT_CANCEL}
              </button>
              <button type="button" className="modal-btn modal-btn-danger" onClick={confirmDelete} disabled={deleting}>
                {deleting ? "..." : TXT_DEL}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Batch delete confirm modal ── */}
      {batchDeleting && selectedIds.size > 0 && !deleteTarget && (
        <div className="modal-overlay">
          <div className="modal-dialog">
            <h3 className="modal-title">{TXT_CONFIRM_DEL_BATCH.replace("{n}", String(selectedIds.size))}</h3>
            <p className="modal-body">
              将删除 <strong>{selectedIds.size}</strong> 份报告（ID: {Array.from(selectedIds).join(", ")}）
            </p>
            <div className="modal-actions">
              <button type="button" className="modal-btn modal-btn-cancel" onClick={() => setBatchDeleting(false)}>
                {TXT_CANCEL}
              </button>
              <button type="button" className="modal-btn modal-btn-danger" onClick={handleBatchDelete}>
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
