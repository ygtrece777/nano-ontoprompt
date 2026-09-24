import axios, { type AxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/stores/authStore'

type ApiClient = {
  get: <T = any>(url: string, config?: AxiosRequestConfig) => Promise<T>
  post: <T = any>(url: string, data?: unknown, config?: AxiosRequestConfig) => Promise<T>
  put: <T = any>(url: string, data?: unknown, config?: AxiosRequestConfig) => Promise<T>
  delete: <T = any>(url: string, config?: AxiosRequestConfig) => Promise<T>
}

function createApiClient(baseURL: string): ApiClient {
  const client = axios.create({ baseURL })
  client.interceptors.request.use(config => {
    const token = sessionStorage.getItem('token')
    if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  })
  client.interceptors.response.use(
    res => res.data.data !== undefined ? res.data.data : res.data,
    err => {
      if (err.response?.status === 401) {
        useAuthStore.getState().logout()
        window.location.href = '/login'
      }
      return Promise.reject(err.response?.data ?? err)
    }
  )
  return {
    get: (url, config) => client.get(url, config) as Promise<any>,
    post: (url, data, config) => client.post(url, data, config) as Promise<any>,
    put: (url, data, config) => client.put(url, data, config) as Promise<any>,
    delete: (url, config) => client.delete(url, config) as Promise<any>,
  }
}

export const apiClient = createApiClient('/api/v1')
export const apiClientV2 = createApiClient('/api/v2')
