import axios from "axios";

/** 全局 axios 实例，`baseURL` 为 `/api/v1`，默认超时 30 秒。 */
const api = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// 响应拦截只记录日志并原样抛出，用户提示由调用方的 onError 负责
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail || error.message || "请求失败";
    console.error("[API Error]", message);
    return Promise.reject(error);
  }
);

export default api;
