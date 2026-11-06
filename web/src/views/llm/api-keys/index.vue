<template>
  <div class="api-keys">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>API密钥管理</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新增密钥</el-button>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" :model="searchForm" class="search-form mb-4">
        <el-form-item label="厂商">
          <el-select v-model="searchForm.provider_id" placeholder="请选择" clearable style="width: 150px">
            <el-option v-for="provider in providerList" :key="provider.id" :label="provider.name" :value="provider.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型">
          <el-select v-model="searchForm.model_id" placeholder="请选择" clearable style="width: 150px">
            <el-option v-for="model in modelList" :key="model.id" :label="model.model_name" :value="model.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务类型">
          <el-select v-model="searchForm.model_service_type" placeholder="请选择" clearable style="width: 150px">
            <el-option label="大语言模型" value="llm" />
            <el-option label="向量模型" value="embedding" />
            <el-option label="流式语音识别" value="streaming_asr" />
            <el-option label="录音文件识别" value="file_asr" />
            <el-option label="语音合成" value="tts" />
            <el-option label="声音复刻" value="voice_clone" />
            <el-option label="P2P实时语音" value="p2p_voice" />
            <el-option label="同声传译" value="translation" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 120px">
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="fetchData">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="provider_name" label="厂商" width="120" />
        <el-table-column label="关联模型" width="150">
          <template #default="{ row }">
            {{ row.model?.model_name || '未关联' }}
          </template>
        </el-table-column>
        <el-table-column label="服务类型" width="130" align="center">
          <template #default="{ row }">
            <el-tag :type="getServiceTypeColor(row.model_service_type)" size="small">
              {{ row.model_service_type_display || row.model_service_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="调用方式" width="150" align="center">
          <template #default="{ row }">
            <el-tag :type="row.call_mode === 'openapi' ? 'primary' : 'info'" size="small">
              {{ row.call_mode_display || row.call_mode }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="api_id" label="API ID" min-width="150" show-overflow-tooltip />
        <el-table-column prop="api_key" label="API Key" min-width="200">
          <template #default="{ row }">
            <el-tag>{{ row.api_key }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="可用性" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_available ? 'success' : 'danger'">
              {{ row.is_available ? '可用' : '不可用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="配额使用" width="180" align="center">
          <template #default="{ row }">
            <div class="quota-info">
              <el-progress
                :percentage="getQuotaPercentage(row)"
                :color="getQuotaColor(row)"
                :stroke-width="8"
              />
              <div class="quota-text">
                {{ row.used_quota }} / {{ row.max_quota }}
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="last_used_at" label="最后使用" width="180" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="280" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">编辑</el-button>
            <el-button type="success" link :icon="RefreshRight" @click="handleResetQuota(row)">重置</el-button>
            <el-button type="warning" link :icon="Connection" @click="handleTest(row)">测试</el-button>
            <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
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

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑密钥' : '新增密钥'" width="700px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="140px">
        <el-form-item label="所属厂商" prop="provider_id">
          <el-select v-model="form.provider_id" placeholder="请选择厂商" style="width: 100%">
            <el-option v-for="provider in providerList" :key="provider.id" :label="provider.name" :value="provider.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="关联模型">
          <el-select v-model="form.model_id" placeholder="请选择模型（可选）" style="width: 100%">
            <el-option v-for="model in modelList" :key="model.id" :label="model.model_name" :value="model.id" />
          </el-select>
          <div class="text-gray text-xs mt-1">选择此API密钥关联的模型，用于模型级别的API密钥管理</div>
        </el-form-item>

        <el-form-item label="服务类型" prop="model_service_type">
          <el-select v-model="form.model_service_type" placeholder="请选择服务类型" style="width: 100%">
            <el-option label="大语言模型" value="llm">
              <div>大语言模型 - 文本生成、对话、问答</div>
            </el-option>
            <el-option label="向量模型" value="embedding">
              <div>向量模型 - 文本向量化、语义搜索</div>
            </el-option>
            <el-option label="流式语音识别" value="streaming_asr">
              <div>流式语音识别 - 实时语音转文字</div>
            </el-option>
            <el-option label="录音文件识别" value="file_asr">
              <div>录音文件识别 - 上传音频文件识别</div>
            </el-option>
            <el-option label="语音合成" value="tts">
              <div>语音合成 - 文字转语音</div>
            </el-option>
            <el-option label="声音复刻" value="voice_clone">
              <div>声音复刻 - 克隆指定人的声音</div>
            </el-option>
            <el-option label="P2P实时语音" value="p2p_voice">
              <div>P2P实时语音 - 点对点实时语音通话</div>
            </el-option>
            <el-option label="同声传译" value="translation">
              <div>同声传译 - 实时语音翻译</div>
            </el-option>
          </el-select>
          <div class="text-gray text-xs mt-1">选择此API密钥提供的服务类型</div>
        </el-form-item>
        
        <el-form-item label="调用方式" prop="call_mode">
          <el-select v-model="form.call_mode" placeholder="请选择调用方式" style="width: 100%">
            <el-option label="OpenAPI 格式" value="openapi">
              <div>OpenAPI 格式 - 使用 openai 库进行访问</div>
            </el-option>
            <el-option label="厂商 SDK 模式" value="vendor_sdk">
              <div>厂商 SDK 模式 - 使用厂商提供的 SDK 进行访问</div>
            </el-option>
          </el-select>
          <div class="text-gray text-xs mt-1">选择调用大模型的方式</div>
        </el-form-item>

        <!-- 认证字段 -->
        <el-divider content-position="left">
          <el-icon><Lock /></el-icon>
          认证信息
        </el-divider>

        <el-form-item label="API ID">
          <el-input v-model="form.api_id" placeholder="如：my_app_001（可选）" />
          <div class="text-gray text-xs mt-1">某些厂商需要的API ID</div>
        </el-form-item>

        <el-form-item label="API Key" prop="api_key">
          <el-input
            v-model="form.api_key"
            type="password"
            :placeholder="isEdit && form.api_key && form.api_key.includes('****') ? '当前显示遮蔽后的值，留空则不修改' : 'sk-...'"
            show-password
          />
          <div v-if="isEdit && form.api_key && form.api_key.includes('****')" class="text-gray text-xs mt-1">
            提示：当前显示遮蔽后的值，如需修改请输入新的 API Key，留空则保持原值不变
          </div>
        </el-form-item>

        <el-form-item label="API Secret">
          <el-input
            v-model="form.api_secret"
            type="password"
            :placeholder="isEdit && form.api_secret && form.api_secret.includes('****') ? '当前显示遮蔽后的值，留空则不修改' : '某些厂商需要'"
            show-password
          />
        </el-form-item>

        <el-form-item label="Access Token">
          <el-input
            v-model="form.access_token"
            type="password"
            :placeholder="isEdit && form.access_token && form.access_token.includes('****') ? '当前显示遮蔽后的值，留空则不修改' : 'OAuth等Token认证（可选）'"
            show-password
          />
        </el-form-item>

        <el-form-item label="端点URL">
          <el-input v-model="form.endpoint_url" placeholder="自定义端点，留空使用默认" />
        </el-form-item>

        <!-- 配额和备注 -->
        <el-divider content-position="left">
          <el-icon><Setting /></el-icon>
          配置
        </el-divider>

        <el-form-item label="每日配额限制" prop="max_quota">
          <el-input-number v-model="form.max_quota" :min="0" :step="10000" style="width: 100%" />
          <div class="text-gray text-xs">tokens/天，0表示不限制</div>
        </el-form-item>

        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 测试结果弹窗 -->
    <el-dialog v-model="testDialogVisible" title="测试结果" width="500px">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="状态">
          <el-tag :type="testResult.available ? 'success' : 'danger'">
            {{ testResult.available ? '可用' : '不可用' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item v-if="!testResult.available" label="原因">
          {{ testResult.reason || '未知错误' }}
        </el-descriptions-item>
        <el-descriptions-item label="剩余配额">
          {{ testResult.remaining_quota || 0 }} tokens
        </el-descriptions-item>
        <el-descriptions-item v-if="testResult.message" label="提示">
          {{ testResult.message }}
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="testDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Plus, Edit, Delete, Search, Refresh, RefreshRight, Connection, Lock, Setting, Service } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getProviderList,
  getModelList,
  getApiKeyList,
  createApiKey,
  updateApiKey,
  deleteApiKey,
  resetApiKeyQuota,
  testApiKey
} from '@/api/llm'

const loading = ref(false)
const tableData = ref([])
const providerList = ref([])
const modelList = ref([])
const dialogVisible = ref(false)
const testDialogVisible = ref(false)
const formRef = ref()
const isEdit = ref(false)

const searchForm = reactive({
  provider_id: null,
  model_id: null,
  model_service_type: null,
  status: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const form = reactive({
  id: null,
  provider_id: null,
  model_id: null,
  model_service_type: 'llm',
  call_mode: 'vendor_sdk',
  // 统一的认证字段
  api_id: '',
  api_key: '',
  api_secret: '',
  access_token: '',
  endpoint_url: '',
  // 其他
  max_quota: 100000,
  description: ''
})

const testResult = reactive({
  available: false,
  reason: '',
  remaining_quota: 0,
  message: ''
})

const rules = {
  provider_id: [{ required: true, message: '请选择厂商', trigger: 'change' }],
  model_service_type: [{ required: true, message: '请选择服务类型', trigger: 'change' }]
  // api_key 不再是必填，因为有些服务可能只需要其他认证方式
}

const fetchData = async () => {
  loading.value = true
  try {
    const { data } = await getApiKeyList({
      ...searchForm,
      page: pagination.page,
      page_size: pagination.pageSize
    })
    tableData.value = data.items || []
    pagination.total = data.total || 0
  } catch (error) {
    ElMessage.error('获取密钥列表失败')
  } finally {
    loading.value = false
  }
}

const fetchProviders = async () => {
  try {
    const { data } = await getProviderList({ page: 1, page_size: 100 })
    providerList.value = data.items || []
  } catch (error) {
    ElMessage.error('获取厂商列表失败')
  }
}

const fetchModels = async () => {
  try {
    const { data } = await getModelList({ page: 1, page_size: 100 })
    modelList.value = data.items || []
  } catch (error) {
    ElMessage.error('获取模型列表失败')
  }
}

const handleAdd = () => {
  // 重置所有字段为默认值
  form.id = null
  form.provider_id = null
  form.model_id = null
  form.model_service_type = 'llm'
  form.call_mode = 'vendor_sdk'
  // 统一的认证字段
  form.api_id = ''
  form.api_key = ''
  form.api_secret = ''
  form.access_token = ''
  form.endpoint_url = ''
  // 其他
  form.max_quota = 100000
  form.description = ''

  isEdit.value = false
  dialogVisible.value = true
}

const handleEdit = (row) => {
  // 编辑时显示遮蔽后的值
  console.log('[handleEdit] 收到的API数据:', row)

  form.id = row.id
  form.provider_id = row.provider_id
  form.model_id = row.model_id ?? null
  form.model_service_type = row.model_service_type || 'llm'
  form.call_mode = row.call_mode || 'vendor_sdk'
  // 统一的认证字段
  form.api_id = row.api_id ?? ''
  form.api_key = row.api_key ?? row.app_key ?? ''
  form.api_secret = row.api_secret ?? ''
  form.access_token = row.access_token ?? ''
  form.endpoint_url = row.endpoint_url ?? ''
  // 其他
  form.max_quota = row.max_quota ?? 100000
  form.description = row.description ?? ''

  console.log('[handleEdit] 设置后的form对象:', JSON.parse(JSON.stringify(form)))

  isEdit.value = true
  dialogVisible.value = true
}

const submit = async () => {
  await formRef.value.validate()
  try {
    if (isEdit.value) {
      const updateData = { ...form }

      // 处理空字符串：转换为null
      const fields = ['api_id', 'api_key', 'api_secret', 'access_token', 'endpoint_url', 'model_id']
      fields.forEach(field => {
        if (updateData[field] === '') {
          updateData[field] = null
        }
      })
      
      // 处理备注字段：允许空字符串，不转换为null
      // description 字段保持原样

      // 处理遮蔽值：如果字段包含****，则不更新该字段
      if (updateData.api_key && updateData.api_key.includes('****')) {
        delete updateData.api_key
      }
      if (updateData.api_secret && updateData.api_secret.includes('****')) {
        delete updateData.api_secret
      }
      if (updateData.access_token && updateData.access_token.includes('****')) {
        delete updateData.access_token
      }

      // 删除 id 字段，因为 URL 中已经包含了
      delete updateData.id

      console.log('[submit] 发送更新请求，数据:', JSON.parse(JSON.stringify(updateData)))
      
      await updateApiKey(form.id, updateData)
      ElMessage.success('更新成功')
      dialogVisible.value = false
      fetchData()  // 刷新列表

    } else {
      await createApiKey(form)
      ElMessage.success('创建成功')
      dialogVisible.value = false
      fetchData()
    }
  } catch (error) {
    console.error('[submit] 更新失败:', error)
    ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确定要删除密钥"${row.api_id}"吗？`, '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      await deleteApiKey(row.id)
      ElMessage.success('删除成功')
      fetchData()
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  })
}

const handleResetQuota = (row) => {
  ElMessageBox.confirm('确定要重置此密钥的配额吗？', '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      await resetApiKeyQuota(row.id)
      ElMessage.success('重置成功')
      fetchData()
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '重置失败')
    }
  })
}

const handleTest = async (row) => {
  try {
    const { data } = await testApiKey(row.id)
    Object.assign(testResult, data)
    testDialogVisible.value = true
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '测试失败')
  }
}

const handleReset = () => {
  searchForm.provider_id = null
  searchForm.model_id = null
  searchForm.model_service_type = null
  searchForm.status = ''
  fetchData()
}

// 辅助函数：获取服务类型颜色
const getServiceTypeColor = (type) => {
  const colors = {
    'llm': 'primary',
    'embedding': 'primary',
    'streaming_asr': 'success',
    'file_asr': 'success',
    'tts': 'warning',
    'voice_clone': 'danger',
    'p2p_voice': 'info',
    'translation': 'warning'
  }
  return colors[type] || 'info'
}

const getQuotaPercentage = (row) => {
  if (row.max_quota === 0) return 0
  return Math.min(100, Math.round((row.used_quota / row.max_quota) * 100))
}

const getQuotaColor = (row) => {
  const percentage = getQuotaPercentage(row)
  if (percentage >= 90) return '#f56c6c'
  if (percentage >= 70) return '#e6a23c'
  return '#67c23a'
}

onMounted(() => {
  fetchProviders()
  fetchModels()
  fetchData()
})
</script>

<style scoped>
.api-keys {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 16px;
}

.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.quota-info {
  padding: 0 10px;
}

.quota-text {
  font-size: 12px;
  color: #606266;
  margin-top: 4px;
}

.text-gray {
  color: #909399;
}

.text-xs {
  font-size: 12px;
}

.mb-4 {
  margin-bottom: 16px;
}

.ml-1 {
  margin-left: 4px;
}
</style>


