import axios from 'axios';

const API_BASE_URL = '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

export const tradingApi = {
  getTickers: async () => {
    const response = await api.get('/trading/tickers');
    return response.data;
  },

  getBars: async (ticker, limit = 100) => {
    const response = await api.get(`/trading/bars/${ticker}?limit=${limit}`);
    return response.data;
  },

  getStatus: async () => {
    const response = await api.get('/trading/status');
    return response.data;
  },
};

export const tubeApi = {
  getStations: async () => {
    const response = await api.get('/tube/stations');
    return response.data;
  },

  findRoute: async ({
    start,
    end,
    routingType = 'time',
    algorithm = 'dijkstra',
  }) => {
    const response = await api.get('/tube/route', {
      params: {
        start,
        end,
        routing_type: routingType,
        algorithm,
      },
    });

    return response.data;
  },
};

export const taskApi = {
  getTask: async (taskId) => {
    const response = await api.get(`/ai/tasks/${taskId}`);
    return response.data;
  },

  approveApproval: async (approvalId) => {
    const response = await api.post(
      `/ai/approvals/${approvalId}/approve`
    );
    return response.data;
  },

  rejectApproval: async (approvalId) => {
    const response = await api.post(
      `/ai/approvals/${approvalId}/reject`
    );
    return response.data;
  },
};

export default api;