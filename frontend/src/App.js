import { useState, useEffect, useCallback } from 'react';
import './App.css';
import {
  fetchTenants, fetchSummary, fetchImportBatches,
  fetchRecords, fetchAuditLogs, uploadCSV,
  approveRecord, rejectRecord, lockRecord, patchRecord,
} from './api';

// ---- Helper text per source type ----
const SOURCE_HELPERS = {
  SAP: 'SAP fuel & procurement flat-file export. Expected columns: BELNR, BUDAT, Werk, MATNR, MAKTX, Menge, MEINS, LIFNR',
  UTILITY: 'Utility portal electricity CSV export. Expected columns: meter_id, account_number, billing_start, billing_end, usage_kwh, demand_kw, tariff, facility',
  TRAVEL: 'Corporate travel (Concur/Navan) export. Expected columns: trip_id, traveler, employee_id, category, booking_date, travel_date, origin, destination, distance_km, hotel_nights, city, country',
};

// Expected header columns for each source type (used for client-side validation)
const EXPECTED_COLUMNS = {
  SAP: ['BELNR', 'BUDAT', 'Werk', 'MATNR', 'MAKTX', 'Menge', 'MEINS', 'LIFNR'],
  UTILITY: ['meter_id', 'account_number', 'billing_start', 'billing_end', 'usage_kwh', 'demand_kw', 'tariff', 'facility'],
  TRAVEL: ['trip_id', 'traveler', 'employee_id', 'category', 'booking_date', 'travel_date', 'origin', 'destination', 'distance_km', 'hotel_nights', 'city', 'country'],
};

// ---- Badge helpers ----
function statusBadgeClass(s) {
  const map = {
    'NEEDS_REVIEW': 'badge-needs-review', 'FLAGGED': 'badge-flagged',
    'APPROVED': 'badge-approved', 'REJECTED': 'badge-rejected', 'LOCKED': 'badge-locked',
    'COMPLETED': 'badge-completed', 'COMPLETED_WITH_ERRORS': 'badge-completed-with-errors',
    'FAILED': 'badge-failed', 'PROCESSING': 'badge-processing',
    'NORMALIZED': 'badge-normalized', 'RAW': 'badge-raw',
  };
  return map[s] || '';
}
function scopeBadgeClass(s) {
  if (s === 'Scope 1') return 'badge-scope1';
  if (s === 'Scope 2') return 'badge-scope2';
  return 'badge-scope3';
}
function confBadgeClass(c) {
  const map = { 'HIGH': 'badge-high', 'MEDIUM': 'badge-medium', 'LOW': 'badge-low' };
  return map[c] || '';
}
function formatDate(d) {
  if (!d) return '—';
  return new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}
function formatDateTime(d) {
  if (!d) return '—';
  return new Date(d).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit'
  });
}
function fmtNum(n) {
  if (n == null) return '—';
  return Number(n).toLocaleString('en-US', { maximumFractionDigits: 1 });
}


const TENANT_STORAGE_KEY = 'breathe_selected_tenant_id';

// Demo tenants used when backend returns no tenants (keeps UI usable in demos)
const DEMO_TENANTS = [
  { id: -1, company_name: 'Acme Corp' },
  { id: -2, company_name: 'BlueGrid Energy' },
  { id: -3, company_name: 'GreenMiles Logistics' },
];

function App() {
  // ---- State ----
  const [tenants, setTenants] = useState([]);
  const [tenantId, setTenantId] = useState(null);
  const [tenantLoadError, setTenantLoadError] = useState('');
  const [summary, setSummary] = useState({});
  const [batches, setBatches] = useState([]);
  const [records, setRecords] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);

  // Upload
  const [uploadSource, setUploadSource] = useState('SAP');
  const [uploadFile, setUploadFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [uploadValid, setUploadValid] = useState(false);

  // Filters
  const [filterSource, setFilterSource] = useState('');
  const [filterScope, setFilterScope] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterConfidence, setFilterConfidence] = useState('');
  const [searchText, setSearchText] = useState('');

  // Detail modal
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [recordAudit, setRecordAudit] = useState([]);
  const [editNotes, setEditNotes] = useState('');

  // Active section tab
  const [activeTab, setActiveTab] = useState('review');

  const updateTenantSelection = useCallback((nextTenantId) => {
    setTenantId(nextTenantId);
    localStorage.setItem(TENANT_STORAGE_KEY, String(nextTenantId));
  }, []);

  // ---- Data fetching ----
  const loadAll = useCallback(async () => {
    if (!tenantId) return;
    try {
      const [sumRes, batchRes, auditRes] = await Promise.all([
        fetchSummary(tenantId),
        fetchImportBatches(tenantId),
        fetchAuditLogs({ tenant: tenantId }),
      ]);
      setSummary(sumRes.data);
      setBatches(batchRes.data);
      setAuditLogs(auditRes.data);
    } catch (e) { console.error(e); }
  }, [tenantId]);

  const loadRecords = useCallback(async () => {
    if (!tenantId) return;
    const params = { tenant: tenantId };
    if (filterSource) params.source_type = filterSource;
    if (filterScope) params.scope = filterScope;
    if (filterStatus) params.review_status = filterStatus;
    if (filterConfidence) params.confidence = filterConfidence;
    if (searchText) params.search = searchText;
    try {
      const res = await fetchRecords(params);
      setRecords(res.data);
    } catch (e) { console.error(e); }
  }, [tenantId, filterSource, filterScope, filterStatus, filterConfidence, searchText]);

  useEffect(() => {
    fetchTenants()
      .then(res => {
        const tenantList = res.data;

        // If no tenants from backend, use demo tenants
        if (tenantList.length === 0) {
          setTenants(DEMO_TENANTS);
          setTenantLoadError('No tenants found on backend — showing demo tenants for UI. Run seed_tenant to create real tenants.');
          setTenantId(null);
          localStorage.removeItem(TENANT_STORAGE_KEY);
          return;
        }

        // We have real tenants from backend
        setTenants(tenantList);
        setTenantLoadError('');

        // Try to restore previously selected tenant
        const savedTenantId = Number(localStorage.getItem(TENANT_STORAGE_KEY));
        const hasSavedTenant = Number.isFinite(savedTenantId) && tenantList.some(t => t.id === savedTenantId);

        if (hasSavedTenant) {
          // Tenant is still available, restore selection
          setTenantId(savedTenantId);
        } else {
          // No saved tenant or it doesn't exist, require user to select
          setTenantId(null);
          localStorage.removeItem(TENANT_STORAGE_KEY);
        }
      })
      .catch(error => {
        console.error(error);
        setTenantLoadError(
          error.response?.data?.error ||
          error.message ||
          'Could not load tenants from the backend.'
        );
      });
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);
  useEffect(() => { loadRecords(); }, [loadRecords]);

  // ---- Actions ----
  const handleUpload = async () => {
    if (!uploadFile) {
      setUploadResult({ error: 'Choose a CSV file before uploading.' });
      return;
    }
    if (!uploadValid) {
      setUploadResult({ error: `Selected file does not look like a ${uploadSource} CSV. Please choose the correct file.` });
      return;
    }
    if (!tenantId) {
      setUploadResult({ error: tenantLoadError || 'Tenant is still loading. Try again in a moment.' });
      return;
    }
    setUploading(true);
    setUploadResult(null);
    try {
      const res = await uploadCSV(uploadFile, uploadSource, tenantId);
      setUploadResult(res.data);
      setUploadFile(null);
      loadAll();
      loadRecords();
    } catch (e) {
      setUploadResult({
        error:
          e.response?.data?.error ||
          e.message ||
          'Upload failed. Check backend URL, CORS settings, and Render logs.',
      });
    }
    setUploading(false);
  };

  // Validate CSV header columns on file/select change
  useEffect(() => {
    if (!uploadFile) {
      setUploadValid(false);
      return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target.result || '';
      const lines = text.split(/\r?\n/);
      if (lines.length === 0) { setUploadValid(false); return; }
      const headerLine = lines.find(l => l && l.trim() !== '') || '';
      const headers = headerLine.split(',').map(h => h.trim().replace(/^"|"$/g, ''));
      const expected = EXPECTED_COLUMNS[uploadSource] || [];
      const headersLower = headers.map(h => h.toLowerCase());
      const expectedLower = expected.map(h => h.toLowerCase());
      // Require that all expected columns are present in the header
      const hasAll = expectedLower.every(col => headersLower.includes(col));
      setUploadValid(hasAll);
    };
    reader.onerror = () => setUploadValid(false);
    reader.readAsText(uploadFile);
  }, [uploadFile, uploadSource]);

  const handleApprove = async (id) => {
    try { await approveRecord(id); loadAll(); loadRecords(); } catch (e) { alert(e.response?.data?.error || 'Error'); }
  };
  const handleReject = async (id) => {
    try { await rejectRecord(id); loadAll(); loadRecords(); } catch (e) { alert(e.response?.data?.error || 'Error'); }
  };
  const handleLock = async (id) => {
    try { await lockRecord(id); loadAll(); loadRecords(); } catch (e) { alert(e.response?.data?.error || 'Error'); }
  };

  const openDetail = async (record) => {
    setSelectedRecord(record);
    setEditNotes(record.analyst_notes || '');
    try {
      const res = await fetchAuditLogs({ record: record.id });
      setRecordAudit(res.data);
    } catch (e) { setRecordAudit([]); }
  };

  const saveNotes = async () => {
    if (!selectedRecord) return;
    try {
      await patchRecord(selectedRecord.id, { analyst_notes: editNotes });
      loadRecords();
      setSelectedRecord({ ...selectedRecord, analyst_notes: editNotes });
    } catch (e) { alert(e.response?.data?.error || 'Cannot edit'); }
  };

  // ---- Render ----
  return (
    <div className="app">
      {/* ---- Header ---- */}
      <header className="header">
        <div className="header-left">
          <h1>ESG Data Review</h1>
          <p>Ingestion · Normalization · Analyst Review · Audit</p>
        </div>
        <div className="header-right">
          <label>Tenant:</label>
          <select className="tenant-select" value={tenantId || ''}
            onChange={e => updateTenantSelection(Number(e.target.value))}
            disabled={tenants.length === 0}>
            {tenantId === null && tenants.length > 0 && <option value="">Select tenant...</option>}
            {!tenantId && tenants.length === 0 && <option value="">Loading tenant...</option>}
            {tenants.map(t => <option key={t.id} value={t.id}>{t.company_name}</option>)}
          </select>
        </div>
      </header>
      {tenantLoadError && (
        <div className="upload-result" style={{marginBottom:'16px'}}>
          <span style={{color:'#f87171'}}>Backend connection issue: {tenantLoadError}</span>
        </div>
      )}

      {/* ---- Stats Row ---- */}
      <div className="stats-row">
        <div className="stat-card"><div className="stat-value">{summary.total_imports || 0}</div><div className="stat-label">Imports</div></div>
        <div className="stat-card"><div className="stat-value">{summary.total_records || 0}</div><div className="stat-label">Records</div></div>
        <div className="stat-card needs-review"><div className="stat-value">{summary.needs_review || 0}</div><div className="stat-label">Needs Review</div></div>
        <div className="stat-card flagged"><div className="stat-value">{summary.flagged || 0}</div><div className="stat-label">Flagged</div></div>
        <div className="stat-card approved"><div className="stat-value">{summary.approved || 0}</div><div className="stat-label">Approved</div></div>
        <div className="stat-card rejected"><div className="stat-value">{summary.rejected || 0}</div><div className="stat-label">Rejected</div></div>
        <div className="stat-card locked"><div className="stat-value">{summary.locked || 0}</div><div className="stat-label">Locked</div></div>
        <div className="stat-card failed"><div className="stat-value">{summary.failed_rows || 0}</div><div className="stat-label">Failed Rows</div></div>
      </div>

      {/* ---- Upload Panel ---- */}
      <div className="panel">
        <div className="panel-header"><h2>Upload Source Data</h2></div>
        <div className="upload-section">
          <div className="upload-field">
            <label>Source Type</label>
            <select className="source-select" value={uploadSource} onChange={e => setUploadSource(e.target.value)}>
              <option value="SAP">SAP Fuel & Procurement</option>
              <option value="UTILITY">Utility Electricity</option>
              <option value="TRAVEL">Corporate Travel</option>
            </select>
          </div>
          <div className="upload-field">
            <label>CSV File</label>
            <input type="file" accept=".csv" className="file-input"
              onChange={e => setUploadFile(e.target.files[0])} />
          </div>
          <button className="btn-upload" onClick={handleUpload} disabled={!uploadFile || uploading || !tenantId || !uploadValid}>
            {uploading ? 'Uploading...' : tenantId ? 'Upload CSV' : 'Waiting for Backend'}
          </button>
        </div>
        <div className="upload-helper">{SOURCE_HELPERS[uploadSource]}</div>
        {uploadFile && !uploadValid && (
          <div className="upload-result" style={{marginTop:'8px'}}>
            <span style={{color:'#f87171'}}>Selected CSV does not match expected columns for {uploadSource}. Upload disabled.</span>
          </div>
        )}
        {uploadResult && (
          <div className="upload-result">
            {uploadResult.error ? (
              <span style={{color:'#f87171'}}>Error: {uploadResult.error}</span>
            ) : (
              <>
                <span className="result-stat">Total: <span>{uploadResult.total_rows}</span></span>
                <span className="result-stat" style={{color:'#4ade80'}}>Accepted: <span>{uploadResult.accepted}</span></span>
                <span className="result-stat" style={{color:'#f59e0b'}}>Flagged: <span>{uploadResult.flagged}</span></span>
                <span className="result-stat" style={{color:'#f87171'}}>Failed: <span>{uploadResult.failed}</span></span>
                <span className="result-stat">Status: <span className={`badge ${statusBadgeClass(uploadResult.status)}`}>{uploadResult.status}</span></span>
              </>
            )}
          </div>
        )}
      </div>

      {/* ---- Section Tabs ---- */}
      <div className="section-tabs">
        <button className={`section-tab ${activeTab === 'review' ? 'active' : ''}`} onClick={() => setActiveTab('review')}>Review Queue</button>
        <button className={`section-tab ${activeTab === 'batches' ? 'active' : ''}`} onClick={() => setActiveTab('batches')}>Import Batches</button>
        <button className={`section-tab ${activeTab === 'audit' ? 'active' : ''}`} onClick={() => setActiveTab('audit')}>Audit Timeline</button>
      </div>

      {/* ---- Review Queue ---- */}
      {activeTab === 'review' && (
        <div className="panel">
          <div className="panel-header">
            <h2>Review Queue</h2>
            <span className="badge-count">{records.length} records</span>
          </div>
          <div className="filter-bar">
            <select className="filter-select" value={filterSource} onChange={e => setFilterSource(e.target.value)}>
              <option value="">All Sources</option>
              <option value="SAP">SAP</option>
              <option value="UTILITY">Utility</option>
              <option value="TRAVEL">Travel</option>
            </select>
            <select className="filter-select" value={filterScope} onChange={e => setFilterScope(e.target.value)}>
              <option value="">All Scopes</option>
              <option value="Scope 1">Scope 1</option>
              <option value="Scope 2">Scope 2</option>
              <option value="Scope 3">Scope 3</option>
            </select>
            <select className="filter-select" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
              <option value="">All Statuses</option>
              <option value="NEEDS_REVIEW">Needs Review</option>
              <option value="FLAGGED">Flagged</option>
              <option value="APPROVED">Approved</option>
              <option value="REJECTED">Rejected</option>
              <option value="LOCKED">Locked</option>
            </select>
            <select className="filter-select" value={filterConfidence} onChange={e => setFilterConfidence(e.target.value)}>
              <option value="">All Confidence</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
            <input className="filter-input" placeholder="Search activity type..."
              value={searchText} onChange={e => setSearchText(e.target.value)} />
          </div>
          {records.length === 0 ? (
            <div className="empty-state">No records found. Upload a CSV to get started.</div>
          ) : (
            <div style={{overflowX:'auto'}}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Activity</th>
                    <th>Period</th>
                    <th className="text-right">Qty (orig)</th>
                    <th>Unit</th>
                    <th className="text-right">Qty (norm)</th>
                    <th>Scope</th>
                    <th className="text-right">kgCO₂e</th>
                    <th>Confidence</th>
                    <th>Flags</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map(r => (
                    <tr key={r.id} className="clickable" onClick={() => openDetail(r)}>
                      <td>{r.source_type}</td>
                      <td>{r.activity_type}</td>
                      <td style={{whiteSpace:'nowrap',fontSize:'12px'}}>
                        {r.period_start ? formatDate(r.period_start) : '—'}
                        {r.period_end && r.period_end !== r.period_start ? ` → ${formatDate(r.period_end)}` : ''}
                      </td>
                      <td className="text-right text-mono">{fmtNum(r.quantity_original)}</td>
                      <td>{r.unit_original}</td>
                      <td className="text-right text-mono">{fmtNum(r.quantity_normalized)}</td>
                      <td><span className={`badge ${scopeBadgeClass(r.scope)}`}>{r.scope}</span></td>
                      <td className="text-right text-mono">{fmtNum(r.estimated_emissions_kgco2e)}</td>
                      <td><span className={`badge ${confBadgeClass(r.confidence)}`}>{r.confidence}</span></td>
                      <td>
                        {(r.flags || []).map((f,i) => <span key={i} className="flag-pill">{f}</span>)}
                      </td>
                      <td><span className={`badge ${statusBadgeClass(r.review_status)}`}>{r.review_status_display || r.review_status}</span></td>
                      <td onClick={e => e.stopPropagation()}>
                        {r.review_status !== 'LOCKED' && r.review_status !== 'APPROVED' && (
                          <button className="btn-action btn-approve" onClick={() => handleApprove(r.id)}>✓</button>
                        )}
                        {r.review_status !== 'LOCKED' && r.review_status !== 'REJECTED' && (
                          <button className="btn-action btn-reject" onClick={() => handleReject(r.id)}>✗</button>
                        )}
                        {r.review_status === 'APPROVED' && (
                          <button className="btn-action btn-lock" onClick={() => handleLock(r.id)}>🔒</button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ---- Import Batches ---- */}
      {activeTab === 'batches' && (
        <div className="panel">
          <div className="panel-header">
            <h2>Import Batches</h2>
            <span className="badge-count">{batches.length} imports</span>
          </div>
          {batches.length === 0 ? (
            <div className="empty-state">No imports yet.</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Source</th>
                  <th>Uploaded</th>
                  <th>Status</th>
                  <th className="text-right">Total</th>
                  <th className="text-right">Accepted</th>
                  <th className="text-right">Failed</th>
                </tr>
              </thead>
              <tbody>
                {batches.map(b => (
                  <tr key={b.id}>
                    <td>{b.original_filename}</td>
                    <td>{b.source_type}</td>
                    <td>{formatDateTime(b.uploaded_at)}</td>
                    <td><span className={`badge ${statusBadgeClass(b.status)}`}>{b.status_display || b.status}</span></td>
                    <td className="text-right text-mono">{b.total_rows}</td>
                    <td className="text-right text-mono" style={{color:'#4ade80'}}>{b.accepted_rows}</td>
                    <td className="text-right text-mono" style={{color: b.failed_rows > 0 ? '#f87171' : '#64748b'}}>{b.failed_rows}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ---- Audit Timeline ---- */}
      {activeTab === 'audit' && (
        <div className="panel">
          <div className="panel-header">
            <h2>Audit Timeline</h2>
            <span className="badge-count">{auditLogs.length} entries</span>
          </div>
          {auditLogs.length === 0 ? (
            <div className="empty-state">No audit entries yet.</div>
          ) : (
            auditLogs.slice(0, 50).map(log => (
              <div key={log.id} className="audit-entry">
                <span className={`badge ${statusBadgeClass(log.action)}`}>{log.action_display || log.action}</span>
                <span className="audit-record">{log.record_summary}</span>
                <span className="audit-actor">{log.actor}</span>
                <span className="audit-time">{formatDateTime(log.timestamp)}</span>
              </div>
            ))
          )}
        </div>
      )}

      {/* ---- Record Detail Modal ---- */}
      {selectedRecord && (
        <div className="modal-overlay" onClick={() => setSelectedRecord(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Record Detail — #{selectedRecord.id}</h3>
              <button className="modal-close" onClick={() => setSelectedRecord(null)}>×</button>
            </div>

            <div className="modal-section">
              <h4>Normalized Fields</h4>
              <div className="detail-grid">
                <div className="detail-item"><span className="detail-label">Source</span><span className="detail-value">{selectedRecord.source_type}</span></div>
                <div className="detail-item"><span className="detail-label">Activity</span><span className="detail-value">{selectedRecord.activity_type}</span></div>
                <div className="detail-item"><span className="detail-label">Category</span><span className="detail-value">{selectedRecord.category || '—'}</span></div>
                <div className="detail-item"><span className="detail-label">Source Record ID</span><span className="detail-value">{selectedRecord.source_record_id || '—'}</span></div>
                <div className="detail-item"><span className="detail-label">Period</span><span className="detail-value">{formatDate(selectedRecord.period_start)} → {formatDate(selectedRecord.period_end)}</span></div>
                <div className="detail-item"><span className="detail-label">Scope</span><span className="detail-value"><span className={`badge ${scopeBadgeClass(selectedRecord.scope)}`}>{selectedRecord.scope}</span></span></div>
                <div className="detail-item"><span className="detail-label">Qty (original)</span><span className="detail-value">{fmtNum(selectedRecord.quantity_original)} {selectedRecord.unit_original}</span></div>
                <div className="detail-item"><span className="detail-label">Qty (normalized)</span><span className="detail-value">{fmtNum(selectedRecord.quantity_normalized)} {selectedRecord.unit_normalized}</span></div>
                <div className="detail-item"><span className="detail-label">Est. kgCO₂e</span><span className="detail-value">{fmtNum(selectedRecord.estimated_emissions_kgco2e)}</span></div>
                <div className="detail-item"><span className="detail-label">Emission Factor</span><span className="detail-value" style={{fontSize:'11px'}}>{selectedRecord.emission_factor_source || '—'}</span></div>
                <div className="detail-item"><span className="detail-label">Confidence</span><span className="detail-value"><span className={`badge ${confBadgeClass(selectedRecord.confidence)}`}>{selectedRecord.confidence}</span></span></div>
                <div className="detail-item"><span className="detail-label">Status</span><span className="detail-value"><span className={`badge ${statusBadgeClass(selectedRecord.review_status)}`}>{selectedRecord.review_status_display || selectedRecord.review_status}</span></span></div>
              </div>
            </div>

            {/* Location Details */}
            {selectedRecord.location_details && Object.keys(selectedRecord.location_details).length > 0 && (
              <div className="modal-section">
                <h4>Location / Context</h4>
                <div className="detail-grid">
                  {Object.entries(selectedRecord.location_details).map(([k,v]) => v ? (
                    <div key={k} className="detail-item"><span className="detail-label">{k}</span><span className="detail-value">{String(v)}</span></div>
                  ) : null)}
                </div>
              </div>
            )}

            {/* Flags */}
            {selectedRecord.flags && selectedRecord.flags.length > 0 && (
              <div className="modal-section">
                <h4>Flags</h4>
                <div>{selectedRecord.flags.map((f,i) => <span key={i} className="flag-pill" style={{fontSize:'12px',padding:'3px 8px'}}>{f}</span>)}</div>
              </div>
            )}

            {/* Raw Source JSON */}
            {selectedRecord.raw_json && (
              <div className="modal-section">
                <h4>Raw Source Data</h4>
                <div className="raw-json">{JSON.stringify(selectedRecord.raw_json, null, 2)}</div>
              </div>
            )}

            {/* Analyst Notes */}
            <div className="modal-section">
              <h4>Analyst Notes</h4>
              {selectedRecord.review_status === 'LOCKED' ? (
                <div style={{color:'#94a3b8', fontSize:'13px'}}>{selectedRecord.analyst_notes || 'No notes'} <span style={{color:'#64748b', fontSize:'11px'}}>(locked — cannot edit)</span></div>
              ) : (
                <>
                  <textarea className="notes-input" value={editNotes} onChange={e => setEditNotes(e.target.value)} placeholder="Add analyst notes..." />
                  <button className="btn-save-notes" onClick={saveNotes}>Save Notes</button>
                </>
              )}
            </div>

            {/* Audit History */}
            <div className="modal-section">
              <h4>Audit History</h4>
              {recordAudit.length === 0 ? (
                <div style={{color:'#475569', fontSize:'12px'}}>No audit entries</div>
              ) : (
                recordAudit.map(log => (
                  <div key={log.id} className="audit-entry">
                    <span className={`badge ${statusBadgeClass(log.action)}`}>{log.action_display || log.action}</span>
                    <span className="audit-actor">{log.actor}</span>
                    <span className="audit-time">{formatDateTime(log.timestamp)}</span>
                    {log.note && <span className="audit-record" style={{fontStyle:'italic'}}>{log.note}</span>}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
