import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include auth token from localStorage
api.interceptors.request.use(
  (config) => {
    // Only add token if we're in the browser (not SSR)
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('auth_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor to handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Token expired or invalid, clear auth and redirect to login
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('user_email');
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

// Health API
export const healthApi = {
  checkHealth: async () => {
    const response = await api.get('/health');
    return response.data;
  },
};
