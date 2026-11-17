import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// 客户门户独立前端：构建产物 customer-portal/dist，部署到 /portal 路径。
// VITE_API_BASE_URL 可覆盖 API 前缀（默认 /api，与主后台一致，由 app_wrapper 剥离）。
const API_BASE = process.env.VITE_API_BASE_URL || '/api'

export default defineConfig({
  plugins: [vue()],
  base: '/portal/',
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') }
  },
  define: {
    __API_BASE__: JSON.stringify(API_BASE)
  },
  server: {
    port: 3100,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:9998',
        changeOrigin: true,
        secure: false
      }
    },
    historyApiFallback: true
  }
})
