import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getSystemConfig } from '@/api/common'

export const useSystemStore = defineStore('system', () => {
  const app_name = ref('AIPanelAdmin')
  const app_version = ref('v0.1.0')
  const app_description = ref('AIPanelAdmin API Documentation')
  const frontend_name = ref('')
  const backend_name = ref('')
  const debug = ref(false)
  const install_redirect = ref('login')
  const enabled_plugins = ref([])
  const loaded = ref(false)

  /**
   * 从后端加载系统公共配置
   * @param {boolean} force - 是否强制刷新
   */
  async function loadConfig(force = false) {
    if (loaded.value && !force) return
    try {
      const res = await getSystemConfig()
      const data = res.data || res
      if (data.app_name != null) app_name.value = data.app_name
      if (data.app_version != null) app_version.value = data.app_version
      if (data.app_description != null) app_description.value = data.app_description
      if (data.frontend_name != null) frontend_name.value = data.frontend_name
      if (data.backend_name != null) backend_name.value = data.backend_name
      if (data.install_redirect != null) install_redirect.value = data.install_redirect
      if (typeof data.debug === 'boolean') debug.value = data.debug
      if (Array.isArray(data.enabled_plugins)) enabled_plugins.value = data.enabled_plugins
      loaded.value = true
    } catch (e) {
      console.warn('[system store] 加载系统配置失败，使用默认值：', e?.message || e)
    }
  }

  const siteTitle = computed(() => backend_name.value || app_name.value)
  const productName = computed(() => frontend_name.value || app_name.value)

  /**
   * 判断插件是否启用
   * @param {string} name - 插件名（如 'approval' / 'mail'）
   */
  function isPluginEnabled(name) {
    return enabled_plugins.value.includes(name)
  }

  return {
    app_name,
    app_version,
    app_description,
    frontend_name,
    backend_name,
    debug,
    install_redirect,
    enabled_plugins,
    loaded,
    loadConfig,
    siteTitle,
    productName,
    isPluginEnabled,
  }
})
