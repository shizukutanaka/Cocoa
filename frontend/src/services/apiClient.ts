import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, InternalAxiosRequestConfig } from 'axios';

const DEFAULT_TIMEOUT_MS = 15000;

export interface ApiClientOptions {
  readonly baseURL?: string;
  readonly getAccessToken?: () => string | null;
  readonly onUnauthorized?: () => void;
}

class ApiClient {
  private readonly instance: AxiosInstance;

  constructor(options: ApiClientOptions = {}) {
    const { baseURL = import.meta.env.VITE_API_BASE_URL, getAccessToken, onUnauthorized } = options;

    this.instance = axios.create({
      baseURL,
      timeout: DEFAULT_TIMEOUT_MS,
      withCredentials: true,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.instance.interceptors.request.use((config: InternalAxiosRequestConfig) => {
      const token = getAccessToken?.();
      if (token) {
        // eslint-disable-next-line no-param-reassign
        config.headers = {
          ...config.headers,
          Authorization: `Bearer ${token}`,
        };
      }
      return config;
    });

    this.instance.interceptors.response.use(
      (response: AxiosResponse) => response,
      (error) => {
        if (error.response?.status === 401) {
          onUnauthorized?.();
        }
        return Promise.reject(error);
      },
    );
  }

  get axios(): AxiosInstance {
    return this.instance;
  }

  get<T = unknown>(url: string, config?: AxiosRequestConfig) {
    return this.instance.get<T>(url, config);
  }
}

export const apiClient = new ApiClient({
  getAccessToken: () => sessionStorage.getItem('cocoa_access_token'),
  onUnauthorized: () => {
    sessionStorage.removeItem('cocoa_access_token');
  },
}).axios;

export type { AxiosResponse };
