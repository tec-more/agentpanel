<template>
  <div class="plugin-management">
    <!-- 搜索栏 -->
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="插件名称">
          <el-input v-model="searchForm.keyword" placeholder="请输入插件名称" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.is_enabled" placeholder="请选择" clearable style="width: 120px">
            <el-option label="已启用" :value="true" />
            <el-option label="已禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>插件列表</span>
          <div class="header-actions">
            <el-button type="success" :icon="RefreshRight" :loading="syncLoading" @click="handleSync">
              同步插件
            </el-button>
            <el-button type="primary" :icon="Upload" @click="showUploadDialog">
              上传插件
            </el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="display_name" label="插件名称" min-width="150">
          <template #default="{ row }">
            <div class="plugin-name">
              <span class="name">{{ row.display_name }}</span>
              <span class="version">v{{ row.version }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="标识符" min-width="120" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="author" label="作者" width="120" />
        <el-table-column label="安装状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_installed ? 'success' : 'info'" size="small">
              {{ row.is_installed ? '已安装' : '未安装' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用状态" width="100" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_enabled"
              :loading="row._switching"
              :disabled="!row.is_installed"
              @change="(val) => handleToggleStatus(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="安装时间" width="180" />
        <el-table-column label="操作" width="220" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              v-if="!row.is_installed"
              type="success"
              link
              :icon="Download"
              :loading="row._installing"
              @click="handleInstall(row)"
            >
              安装
            </el-button>
            <el-button
              type="primary"
              link
              :icon="Setting"
              :disabled="!row.is_enabled"
              @click="handleSettings(row)"
            >
              设置
            </el-button>
            <el-button
              type="danger"
              link
              :icon="Delete"
              :disabled="!row.is_installed"
              @click="handleUninstall(row)"
            >
              卸载
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>

    <!-- 上传插件弹窗 -->
    <el-dialog v-model="uploadDialogVisible" title="上传插件" width="500px">
      <el-upload
        ref="uploadRef"
        class="plugin-upload"
        drag
        :auto-upload="false"
        :limit="1"
        accept=".zip"
        :on-change="handleFileChange"
        :on-exceed="handleExceed"
      >
        <el-icon class="el-icon--upload"><Upload /></el-icon>
        <div class="el-upload__text">
          将插件包拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            只支持 .zip 格式的插件包
          </div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploadLoading" :disabled="!selectedFile" @click="handleUpload">
          安装
        </el-button>
      </template>
    </el-dialog>

    <!-- 插件设置弹窗 -->
    <el-dialog v-model="settingsDialogVisible" :title="`${currentPlugin?.display_name} - 设置`" width="600px">
      <div v-if="settingsLoading" v-loading="settingsLoading" style="min-height: 200px;"></div>
      <template v-else>
        <el-empty v-if="!settingsSchema || Object.keys(settingsSchema).length === 0" description="该插件暂无可配置项" />
        <el-form v-else ref="settingsFormRef" :model="settingsForm" label-width="120px">
          <el-form-item
            v-for="(config, key) in settingsSchema"
            :key="key"
            :label="config.label || key"
            :prop="key"
          >
            <template v-if="config.type === 'boolean'">
              <el-switch v-model="settingsForm[key]" />
            </template>
            <template v-else-if="config.type === 'number'">
              <el-input-number
                v-model="settingsForm[key]"
                :min="config.min"
                :max="config.max"
                :step="config.step || 1"
              />
            </template>
            <template v-else-if="config.type === 'select'">
              <el-select v-model="settingsForm[key]" style="width: 100%">
                <el-option
                  v-for="opt in config.options"
                  :key="opt.value"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
            </template>
            <template v-else-if="config.type === 'textarea'">
              <el-input v-model="settingsForm[key]" type="textarea" :rows="3" />
            </template>
            <template v-else>
              <el-input v-model="settingsForm[key]" :placeholder="config.placeholder" />
            </template>
            <div v-if="config.description" class="setting-description">{{ config.description }}</div>
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="settingsDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="settingsSaveLoading"
          :disabled="!settingsSchema || Object.keys(settingsSchema).length === 0"
          @click="handleSaveSettings"
        >
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, RefreshRight, Upload, Setting, Delete, Download } from '@element-plus/icons-vue'
import {
  getPluginList,
  syncPlugins,
  enablePlugin,
  disablePlugin,
  installPlugin,
  uninstallPlugin,
  uploadPlugin,
  getPluginSettings,
  updatePluginSettings
} from '@/api/plugin'

const loading = ref(false)
const syncLoading = ref(false)
const uploadLoading = ref(false)
const settingsLoading = ref(false)
const settingsSaveLoading = ref(false)
const uploadDialogVisible = ref(false)
const settingsDialogVisible = ref(false)
const uploadRef = ref(null)
const settingsFormRef = ref(null)

const tableData = ref([])
const selectedFile = ref(null)
const currentPlugin = ref(null)
const settingsSchema = ref(null)
const settingsForm = reactive({})

const searchForm = reactive({
  keyword: '',
  is_enabled: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getPluginList({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    })
    tableData.value = (res.data.items || []).map(item => ({
      ...item,
      _switching: false,
      _installing: false
    }))
    pagination.total = res.data.total || 0
  } catch (e) {
    // 错误已处理
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.keyword = ''
  searchForm.is_enabled = null
  handleSearch()
}

const handleSync = async () => {
  syncLoading.value = true
  try {
    const res = await syncPlugins()
    ElMessage.success(res.msg || '同步成功')
    fetchData()
  } catch (e) {
    // 错误已处理
  } finally {
    syncLoading.value = false
  }
}

const handleToggleStatus = async (row, enabled) => {
  row._switching = true
  try {
    if (enabled) {
      await enablePlugin(row.id)
      ElMessage.success('插件已启用')
    } else {
      await disablePlugin(row.id)
      ElMessage.success('插件已禁用')
    }
    fetchData()
  } catch (e) {
    // 恢复原状态
    row.is_enabled = !enabled
  } finally {
    row._switching = false
  }
}

const handleInstall = async (row) => {
  row._installing = true
  try {
    await ElMessageBox.confirm(
      `确定要安装插件 "${row.display_name}" 吗？安装后需手动启用方可生效。`,
      '安装确认',
      { type: 'info', confirmButtonText: '安装', cancelButtonText: '取消' }
    )
  } catch (e) {
    row._installing = false
    return
  }
  try {
    const res = await installPlugin(row.id)
    ElMessage.success(res.msg || '插件安装成功')
    fetchData()
  } catch (e) {
    // 错误已处理
    row._installing = false
  }
}

const handleUninstall = async (row) => {
  // 卸载前置确认 + 登录密码验证
  let password = ''
  try {
    const { value } = await ElMessageBox.prompt(
      `卸载插件 "${row.display_name}" 后将停止使用，需验证您的登录密码。\n请输入当前管理员登录密码：`,
      '卸载确认',
      {
        confirmButtonText: '确认卸载',
        cancelButtonText: '取消',
        type: 'warning',
        inputType: 'password',
        inputPlaceholder: '请输入登录密码',
        inputValidator: (val) => (val && val.trim() ? true : '密码不能为空'),
      }
    )
    password = value
  } catch (e) {
    return // 用户取消
  }

  try {
    const res = await uninstallPlugin(row.id, password)
    ElMessage.success(res.msg || '插件已卸载')
    fetchData()
  } catch (e) {
    // 密码错误或权限不足，错误已由拦截器提示
  }
}

const showUploadDialog = () => {
  selectedFile.value = null
  uploadRef.value?.clearFiles()
  uploadDialogVisible.value = true
}

const handleFileChange = (file) => {
  selectedFile.value = file.raw
}

const handleExceed = () => {
  ElMessage.warning('只能上传一个插件包')
}

const handleUpload = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请选择插件包')
    return
  }

  uploadLoading.value = true
  try {
    const res = await uploadPlugin(selectedFile.value)
    ElMessage.success(res.msg || '插件安装成功')
    uploadDialogVisible.value = false
    fetchData()
  } catch (e) {
    // 错误已处理
  } finally {
    uploadLoading.value = false
  }
}

const handleSettings = async (row) => {
  currentPlugin.value = row
  settingsDialogVisible.value = true
  settingsLoading.value = true

  // 重置表单
  Object.keys(settingsForm).forEach(key => delete settingsForm[key])

  try {
    const res = await getPluginSettings(row.id)
    settingsSchema.value = res.data.schema || {}
    const settings = res.data.settings || {}

    // 初始化表单值
    Object.keys(settingsSchema.value).forEach(key => {
      const config = settingsSchema.value[key]
      settingsForm[key] = settings[key] !== undefined ? settings[key] : config.default
    })
  } catch (e) {
    settingsSchema.value = null
  } finally {
    settingsLoading.value = false
  }
}

const handleSaveSettings = async () => {
  settingsSaveLoading.value = true
  try {
    await updatePluginSettings(currentPlugin.value.id, { ...settingsForm })
    ElMessage.success('设置已保存')
    settingsDialogVisible.value = false
  } catch (e) {
    // 错误已处理
  } finally {
    settingsSaveLoading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style lang="scss" scoped>
.plugin-management {
  .search-card {
    margin-bottom: 16px;

    .search-form {
      display: flex;
      flex-wrap: wrap;

      .el-form-item {
        margin-bottom: 0;
        margin-right: 16px;
      }
    }
  }

  .table-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .header-actions {
        display: flex;
        gap: 12px;
      }
    }
  }

  .pagination-wrapper {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }

  .plugin-name {
    .name {
      font-weight: 500;
    }

    .version {
      margin-left: 8px;
      color: #909399;
      font-size: 12px;
    }
  }

  .plugin-upload {
    width: 100%;

    :deep(.el-upload-dragger) {
      width: 100%;
    }
  }

  .setting-description {
    color: #909399;
    font-size: 12px;
    margin-top: 4px;
  }
}
</style>


