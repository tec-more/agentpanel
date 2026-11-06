<template>
  <div class="llm-models">
    <!-- 厂商管理 -->
    <el-card shadow="never" class="card-spacing">
      <template #header>
        <div class="card-header">
          <span>AI厂商列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAddProvider">新增厂商</el-button>
        </div>
      </template>

      <el-table v-loading="providerLoading" :data="providerList" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="name" label="厂商名称" min-width="120" />
        <el-table-column prop="name_en" label="英文标识" min-width="120" />
        <el-table-column label="Logo" width="100" align="center">
          <template #default="{ row }">
            <el-image v-if="row.logo_url" :src="row.logo_url" style="width: 40px; height: 40px" fit="contain" />
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="official_url" label="官网" min-width="150" show-overflow-tooltip />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="handleEditProvider(row)">编辑</el-button>
            <el-button type="danger" link :icon="Delete" @click="handleDeleteProvider(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 模型管理 -->
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>大模型列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAddModel">新增模型</el-button>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" :model="searchForm" class="search-form mb-4">
        <el-form-item label="厂商">
          <el-select v-model="searchForm.provider_id" placeholder="请选择" clearable style="width: 150px">
            <el-option v-for="provider in providerList" :key="provider.id" :label="provider.name" :value="provider.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 120px">
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="fetchModels">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table v-loading="modelLoading" :data="modelList" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="provider_name" label="厂商" width="120" />
        <el-table-column prop="model_id" label="模型标识" min-width="150" />
        <el-table-column prop="model_name" label="模型名称" min-width="150" />
        <el-table-column prop="endpoint_url" label="访问地址" min-width="200" show-overflow-tooltip />
        <el-table-column label="价格(元/1K)" width="150" align="center">
          <template #default="{ row }">
            <div>输入: ¥{{ row.input_price }}</div>
            <div>输出: ¥{{ row.output_price }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="context_length" label="上下文" width="100" align="center">
          <template #default="{ row }">
            {{ formatContextLength(row.context_length) }}
          </template>
        </el-table-column>
        <el-table-column label="特性" width="180" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.supports_streaming" type="success" size="small">流式</el-tag>
            <el-tag v-if="row.supports_vision" type="warning" size="small">视觉</el-tag>
            <el-tag v-if="row.supports_function" type="info" size="small">函数</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="handleEditModel(row)">编辑</el-button>
            <el-button type="danger" link :icon="Delete" @click="handleDeleteModel(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="modelPagination.page"
          v-model:page-size="modelPagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="modelPagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchModels"
          @current-change="fetchModels"
        />
      </div>
    </el-card>

    <!-- 厂商编辑弹窗 -->
    <el-dialog v-model="providerDialogVisible" :title="providerForm.id ? '编辑厂商' : '新增厂商'" width="600px">
      <el-form ref="providerFormRef" :model="providerForm" :rules="providerRules" label-width="100px">
        <el-form-item label="厂商名称" prop="name">
          <el-input v-model="providerForm.name" placeholder="如：OpenAI" />
        </el-form-item>
        <el-form-item label="英文标识" prop="name_en">
          <el-input v-model="providerForm.name_en" placeholder="如：openai" />
        </el-form-item>
        <el-form-item label="Logo URL">
          <el-input v-model="providerForm.logo_url" placeholder="厂商Logo地址" />
        </el-form-item>
        <el-form-item label="官方网站">
          <el-input v-model="providerForm.official_url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="providerForm.status">
            <el-radio label="active">启用</el-radio>
            <el-radio label="inactive">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="providerForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="providerDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitProvider">确定</el-button>
      </template>
    </el-dialog>

    <!-- 模型编辑弹窗 -->
    <el-dialog v-model="modelDialogVisible" :title="modelForm.id ? '编辑模型' : '新增模型'" width="700px">
      <el-form ref="modelFormRef" :model="modelForm" :rules="modelRules" label-width="120px">
        <el-form-item label="所属厂商" prop="provider_id">
          <el-select v-model="modelForm.provider_id" placeholder="请选择厂商" style="width: 100%">
            <el-option v-for="provider in providerList" :key="provider.id" :label="provider.name" :value="provider.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型标识" prop="model_id">
          <el-input v-model="modelForm.model_id" placeholder="如：gpt-4" />
        </el-form-item>
        <el-form-item label="模型名称" prop="model_name">
          <el-input v-model="modelForm.model_name" placeholder="如：GPT-4" />
        </el-form-item>
        <el-form-item label="访问地址">
          <el-input v-model="modelForm.endpoint_url" placeholder="模型专用访问地址，留空则使用API密钥或厂商默认地址" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="输入价格" prop="input_price">
              <el-input-number v-model="modelForm.input_price" :min="0" :step="0.0001" :precision="4" style="width: 100%" />
              <div class="text-gray text-xs">元/1K tokens</div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="输出价格" prop="output_price">
              <el-input-number v-model="modelForm.output_price" :min="0" :step="0.0001" :precision="4" style="width: 100%" />
              <div class="text-gray text-xs">元/1K tokens</div>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="上下文长度" prop="context_length">
          <el-input-number v-model="modelForm.context_length" :min="0" :step="1024" style="width: 100%" />
        </el-form-item>
        <el-form-item label="支持特性">
          <el-checkbox v-model="modelForm.supports_streaming">流式输出</el-checkbox>
          <el-checkbox v-model="modelForm.supports_vision">视觉识别</el-checkbox>
          <el-checkbox v-model="modelForm.supports_function">函数调用</el-checkbox>
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="modelForm.status">
            <el-radio label="active">启用</el-radio>
            <el-radio label="inactive">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="模型描述">
          <el-input v-model="modelForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="modelDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitModel">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Plus, Edit, Delete, Search, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getProviderList,
  createProvider,
  updateProvider,
  deleteProvider,
  getModelList,
  createModel,
  updateModel,
  deleteModel
} from '@/api/llm'

// 厂商相关
const providerLoading = ref(false)
const providerList = ref([])
const providerDialogVisible = ref(false)
const providerFormRef = ref()
const providerForm = reactive({
  id: null,
  name: '',
  name_en: '',
  logo_url: '',
  official_url: '',
  status: 'active',
  description: ''
})

const providerRules = {
  name: [{ required: true, message: '请输入厂商名称', trigger: 'blur' }],
  name_en: [{ required: true, message: '请输入英文标识', trigger: 'blur' }]
}

// 模型相关
const modelLoading = ref(false)
const modelList = ref([])
const modelDialogVisible = ref(false)
const modelFormRef = ref()
const searchForm = reactive({
  provider_id: null,
  status: ''
})
const modelPagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})
const modelForm = reactive({
  id: null,
  provider_id: null,
  model_id: '',
  model_name: '',
  endpoint_url: '',
  context_length: 4096,
  input_price: 0,
  output_price: 0,
  supports_streaming: true,
  supports_vision: false,
  supports_function: false,
  status: 'active',
  description: ''
})

const modelRules = {
  provider_id: [{ required: true, message: '请选择厂商', trigger: 'change' }],
  model_id: [{ required: true, message: '请输入模型标识', trigger: 'blur' }],
  model_name: [{ required: true, message: '请输入模型名称', trigger: 'blur' }]
}

// 获取厂商列表
const fetchProviders = async () => {
  providerLoading.value = true
  try {
    const { data } = await getProviderList({ page: 1, page_size: 100 })
    providerList.value = data.items || []
  } catch (error) {
    ElMessage.error('获取厂商列表失败')
  } finally {
    providerLoading.value = false
  }
}

// 获取模型列表
const fetchModels = async () => {
  modelLoading.value = true
  try {
    const { data } = await getModelList({
      ...searchForm,
      page: modelPagination.page,
      page_size: modelPagination.pageSize
    })
    modelList.value = data.items || []
    modelPagination.total = data.total || 0
  } catch (error) {
    ElMessage.error('获取模型列表失败')
  } finally {
    modelLoading.value = false
  }
}

// 厂商操作
const handleAddProvider = () => {
  Object.assign(providerForm, {
    id: null,
    name: '',
    name_en: '',
    logo_url: '',
    official_url: '',
    status: 'active',
    description: ''
  })
  providerDialogVisible.value = true
}

const handleEditProvider = (row) => {
  Object.assign(providerForm, row)
  providerDialogVisible.value = true
}

const submitProvider = async () => {
  await providerFormRef.value.validate()
  try {
    if (providerForm.id) {
      await updateProvider(providerForm.id, providerForm)
      ElMessage.success('更新成功')
    } else {
      await createProvider(providerForm)
      ElMessage.success('创建成功')
    }
    providerDialogVisible.value = false
    fetchProviders()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

const handleDeleteProvider = (row) => {
  ElMessageBox.confirm(`确定要删除厂商"${row.name}"吗？`, '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      await deleteProvider(row.id)
      ElMessage.success('删除成功')
      fetchProviders()
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  })
}

// 模型操作
const handleAddModel = () => {
  Object.assign(modelForm, {
    id: null,
    provider_id: null,
    model_id: '',
    model_name: '',
    endpoint_url: '',
    context_length: 4096,
    input_price: 0,
    output_price: 0,
    supports_streaming: true,
    supports_vision: false,
    supports_function: false,
    status: 'active',
    description: ''
  })
  modelDialogVisible.value = true
}

const handleEditModel = (row) => {
  Object.assign(modelForm, row)
  modelDialogVisible.value = true
}

const submitModel = async () => {
  await modelFormRef.value.validate()
  try {
    if (modelForm.id) {
      await updateModel(modelForm.id, modelForm)
      ElMessage.success('更新成功')
    } else {
      await createModel(modelForm)
      ElMessage.success('创建成功')
    }
    modelDialogVisible.value = false
    fetchModels()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  }
}

const handleDeleteModel = (row) => {
  ElMessageBox.confirm(`确定要删除模型"${row.model_name}"吗？`, '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      await deleteModel(row.id)
      ElMessage.success('删除成功')
      fetchModels()
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  })
}

const handleReset = () => {
  searchForm.provider_id = null
  searchForm.status = ''
  fetchModels()
}

const formatContextLength = (value) => {
  if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M'
  if (value >= 1000) return (value / 1000).toFixed(1) + 'K'
  return value
}

onMounted(() => {
  fetchProviders()
  fetchModels()
})
</script>

<style scoped>
.llm-models {
  padding: 20px;
}

.card-spacing {
  margin-bottom: 20px;
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

.text-gray {
  color: #909399;
}

.text-xs {
  font-size: 12px;
}

.mb-4 {
  margin-bottom: 16px;
}
</style>


