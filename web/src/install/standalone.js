/**
 * 安装向导独立入口。
 * 与主 SPA（index.html / main.js）完全分离：不注册主路由、不加载菜单/用户 store，
 * 仅挂载安装组件本身，确保安装页是独立页面、可单独加载。
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import InstallApp from './Index.vue'

const app = createApp(InstallApp)
const pinia = createPinia()

// 注册所有图标（安装页用到的 Element Plus 图标）
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(pinia)
app.use(ElementPlus, { locale: zhCn })

app.mount('#install-app')
