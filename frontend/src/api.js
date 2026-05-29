import axios from 'axios';

const API_BASE = (
  process.env.REACT_APP_API_BASE_URL ||
  'https://breathe-esg-assignment-app.onrender.com'
).replace(/\/$/, '');

const api = axios.create({
  baseURL: `${API_BASE}/api/`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ---- Tenants ----
export const fetchTenants = () => api.get('tenants/');

// ---- Import Batches ----
export const fetchImportBatches = (tenantId) =>
  api.get('import-batches/', { params: { tenant: tenantId } });

// ---- Upload ----
export const uploadCSV = (file, sourceType, tenantId) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('source_type', sourceType);
  formData.append('tenant_id', tenantId);
  return api.post('upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

// ---- Records ----
export const fetchRecords = (params) =>
  api.get('records/', { params });

export const fetchRecordDetail = (id) =>
  api.get(`records/${id}/`);

export const patchRecord = (id, data) =>
  api.patch(`records/${id}/`, data);

export const approveRecord = (id) =>
  api.post(`records/${id}/approve/`);

export const rejectRecord = (id) =>
  api.post(`records/${id}/reject/`);

export const lockRecord = (id) =>
  api.post(`records/${id}/lock/`);

// ---- Raw Records ----
export const fetchRawRecords = (batchId) =>
  api.get('raw-records/', { params: { batch: batchId } });

// ---- Audit ----
export const fetchAuditLogs = (params) =>
  api.get('audit/', { params });

// ---- Summary ----
export const fetchSummary = (tenantId) =>
  api.get('summary/', { params: { tenant: tenantId } });

export default api;
