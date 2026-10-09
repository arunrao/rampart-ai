import axios from 'axios';
import { API_URL, CSRF_HEADER, CSRF_HEADER_VALUE } from '@/utils/auth';

// The dashboard session is an HttpOnly cookie set by the backend's OAuth callback.
// `withCredentials` sends it; the X-Requested-With header satisfies the backend's CSRF
// check on state-changing requests. No token is ever held in JavaScript.
export const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
    [CSRF_HEADER]: CSRF_HEADER_VALUE,
  },
});

// Add response interceptor to handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Session expired or invalid: send the user back to login
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// Observability API
export const observabilityApi = {
  getTraces: async (params?: any) => {
    const response = await api.get('/traces', { params });
    return response.data;
  },
  getTrace: async (traceId: string) => {
    const response = await api.get(`/traces/${traceId}`);
    return response.data;
  },
  getTraceSpans: async (traceId: string) => {
    const response = await api.get(`/traces/${traceId}/spans`);
    return response.data;
  },
  getAnalyticsSummary: async () => {
    const response = await api.get('/analytics/summary');
    return response.data;
  },
};

// Security API
export const securityApi = {
  analyzeContent: async (data: {
    content: string;
    context_type: string;
    trace_id?: string;
    metadata?: any;
  }) => {
    const response = await api.post('/analyze', data);
    return response.data;
  },
  getIncidents: async (params?: any) => {
    const response = await api.get('/incidents', { params });
    return response.data;
  },
  getIncident: async (incidentId: string) => {
    const response = await api.get(`/incidents/${incidentId}`);
    return response.data;
  },
  updateIncidentStatus: async (incidentId: string, status: string) => {
    const response = await api.patch(`/incidents/${incidentId}/status`, null, {
      params: { status },
    });
    return response.data;
  },
  getSecurityStats: async () => {
    const response = await api.get('/stats');
    return response.data;
  },
};

// Policy API
export const policyApi = {
  getPolicies: async (params?: any) => {
    const response = await api.get('/policies', { params });
    return response.data;
  },
  getPolicy: async (policyId: string) => {
    const response = await api.get(`/policies/${policyId}`);
    return response.data;
  },
  createPolicy: async (data: any) => {
    const response = await api.post('/policies', data);
    return response.data;
  },
  updatePolicy: async (policyId: string, data: any) => {
    const response = await api.put(`/policies/${policyId}`, data);
    return response.data;
  },
  deletePolicy: async (policyId: string) => {
    const response = await api.delete(`/policies/${policyId}`);
    return response.data;
  },
  togglePolicy: async (policyId: string) => {
    const response = await api.patch(`/policies/${policyId}/toggle`);
    return response.data;
  },
  evaluatePolicies: async (data: any) => {
    const response = await api.post('/policies/evaluate', data);
    return response.data;
  },
  getTemplates: async () => {
    const response = await api.get('/policies/templates');
    return response.data;
  },
  createFromTemplate: async (template: string) => {
    const response = await api.post(`/policies/templates/${template}`);
    return response.data;
  },
};

// Content Filter API
export const contentFilterApi = {
  filterContent: async (data: {
    content: string;
    filters: string[];
    redact?: boolean;
    trace_id?: string;
  }) => {
    const response = await api.post('/filter', data);
    return response.data;
  },
  /** Public playground — no auth. Uses `fetch` so missing auth never triggers axios 401 redirect. */
  filterContentDemo: async (data: {
    content: string;
    filters: string[];
    redact?: boolean;
    toxicity_threshold?: number;
  }) => {
    const res = await fetch(`${API_URL}/filter/demo`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    const text = await res.text();
    let payload: unknown = null;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      payload = { detail: text };
    }
    if (!res.ok) {
      const err = payload as { detail?: string };
      throw new Error(
        typeof err?.detail === 'string'
          ? err.detail
          : `Demo request failed (${res.status})`
      );
    }
    return payload;
  },
  detectPII: async (content: string) => {
    const response = await api.post('/pii/detect', null, {
      params: { content },
    });
    return response.data;
  },
  redactPII: async (content: string) => {
    const response = await api.post('/pii/redact', null, {
      params: { content },
    });
    return response.data;
  },
  analyzeToxicity: async (content: string) => {
    const response = await api.post('/toxicity/analyze', null, {
      params: { content },
    });
    return response.data;
  },
  getFilterStats: async () => {
    const response = await api.get('/filter/stats');
    return response.data;
  },
};

// Super-admin API (requires caller's email in SUPER_ADMIN_EMAILS)
export type AdminRange = '24h' | '7d' | '30d' | '90d';

export const adminApi = {
  getStats: async (range: AdminRange) => {
    const response = await api.get('/admin/stats', { params: { range } });
    return response.data;
  },
  getTimeseries: async (range: AdminRange) => {
    const response = await api.get('/admin/timeseries', { params: { range } });
    return response.data;
  },
  getCostByUser: async (range: AdminRange, limit = 25) => {
    const response = await api.get('/admin/cost/by-user', { params: { range, limit } });
    return response.data;
  },
  getCostByEndpoint: async (range: AdminRange) => {
    const response = await api.get('/admin/cost/by-endpoint', { params: { range } });
    return response.data;
  },
  getAuditLogs: async (params?: {
    limit?: number;
    offset?: number;
    endpoint?: string;
    user_id?: string;
    event_type?: string;
    errors_only?: boolean;
  }) => {
    const response = await api.get('/admin/audit-logs', { params });
    return response.data;
  },
  getUsers: async (params?: {
    limit?: number;
    offset?: number;
    search?: string;
    sort?: 'created_at' | 'cost_usd' | 'requests' | 'last_seen';
  }) => {
    const response = await api.get('/admin/users', { params });
    return response.data;
  },
};

// Health API
export const healthApi = {
  checkHealth: async () => {
    const response = await api.get('/health');
    return response.data;
  },
};
