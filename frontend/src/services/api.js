/**
 * API Service - Axios Instance Configuration
 * ============================================
 * 封装所有 HTTP 请求的基础配置和拦截器
 */

import axios from 'axios';

// Create axios instance with default config
const api = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000/api/v1',
  timeout: 30000, // 30 seconds
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add authentication token if available
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // Add request timestamp for debugging
    config.headers['X-Request-Time'] = new Date().toISOString();
    
    return config;
  },
  (error) => {
    console.error('❌ Request interceptor error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    // Log successful response
    console.log(`✅ [${response.status}] ${response.config.method?.toUpperCase()} ${response.config.url}`);
    return response;
  },
  (error) => {
    // Handle common errors
    if (error.response) {
      const { status, data } = error.response;
      
      switch (status) {
        case 400:
          console.error('❌ Bad Request:', data.detail || data.message);
          break;
        case 401:
          console.error('❌ Unauthorized - Token expired');
          // TODO: Redirect to login or refresh token
          break;
        case 404:
          console.error('❌ Resource not found');
          break;
        case 500:
          console.error('❌ Internal Server Error');
          break;
        default:
          console.error(`❌ HTTP Error ${status}:`, data);
      }
    } else if (error.request) {
      console.error('❌ No response received:', error.request);
    } else {
      console.error('❌ Request error:', error.message);
    }
    
    return Promise.reject(error);
  }
);

export default api;
