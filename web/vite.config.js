import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import path from 'path'

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      resolvers: [ElementPlusResolver()],
      imports: ['vue', 'vue-router', 'pinia'],
      dts: 'src/auto-imports.d.ts'
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: 'src/components.d.ts'
    }),
    // 开发态：让裸路径 /install 直接命中独立的安装页 install.html，
    // 与生产由后端 app_wrapper 提供 install.html 的行为保持一致，避免 SPA 回退死循环。
    {
      name: 'rewrite-install-route',
      enforce: 'pre',
      configureServer(server) {
        server.middlewares.use((req, _res, next) => {
          if (req.url === '/install' || req.url === '/install/') {
            req.url = '/install.html'
          }
          next()
        })
      }
    }
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  build: {
    // 多入口：主应用 index.html 与独立安装页 install.html 分开打包，
    // 保证安装向导是独立页面、不混入主 SPA 产物。
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'index.html'),
        install: path.resolve(__dirname, 'install.html')
      }
    }
  },
  define: {
    __DEFAULT_EDGE_TYPE__: JSON.stringify('smoothstep') 
    // 全局默认连线类型：阶梯线
    // straight , step , bezier , smoothbezier , smoothstep
  },
  server: {
    port: 3000,
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
