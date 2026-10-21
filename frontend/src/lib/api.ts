import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

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
