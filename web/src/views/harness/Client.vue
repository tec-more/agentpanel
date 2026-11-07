<template>
  <div class="harness-client">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 130px">
            <el-option label="启用" value="active" />
            <el-option label="已吊销" value="revoked" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
          <el-button type="success" :icon="Plus" @click="openCreate">签发凭据</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header><span>Harness 客户端凭据</span></template>
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="client_id" label="client_id" width="200" show-overflow-tooltip />
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column prop="secret_prefix" label="secret 前缀" width="130" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '启用' : '已吊销' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="授权范围" min-width="140">
          <template #default="{ row }">
            <el-tag v-for="s in row.scopes" :key="s" size="small" style="margin-right: 4px">{{ s }}</el-tag>
            <span v-if="!row.scopes?.length">-</span>
          </template>
        </el-table-column>
        <el-table-column label="IP 白名单" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.allowed_ips?.join(', ') || '不限' }}</template>
        </el-table-column>
        <el-table-column prop="expires_at" label="过期时间" width="175">
          <template #default="{ row }">{{ row.expires_at || '永久' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="175" />
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button
              type="danger"
              link
              :icon="Delete"
              :disabled="row.status !== 'active'"
              @click="handleRevoke(row)"
            >吊销</el-button>
          </template>
        </el-table-column>
      </el-table>
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

    <el-dialog v-model="createVisible" title="签发客户端凭据" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如 deepseek-harness-prod" />
        </el-form-item>
        <el-form-item label="授权范围">
          <el-select v-model="form.scopes" multiple filterable allow-create default-first-option
                     placeholder="可输入自定义 scope" style="width: 100%">
            <el-option label="session" value="session" />
            <el-option label="run" value="run" />
            <el-option label="event" value="event" />
            <el-option label="approval" value="approval" />
          </el-select>
        </el-form-item>
        <el-form-item label="IP 白名单">
          <el-select v-model="form.allowed_ips" multiple filterable allow-create default-first-option
                     placeholder="留空不限" style="width: 100%" />
        </el-form-item>
        <el-form-item label="过期时间">
          <el-date-picker
            v-model="form.expires_at"
            type="datetime"
            placeholder="留空永久有效"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleCreate">签发</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="secretVisible" title="凭据已签发（仅此一次回显）" width="640px" :close-on-click-modal="false">
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="secret 只在本次回显，关闭后无法再次获取；请立即保存到 Harness 运行环境。"
        style="margin-bottom: 12px"
      />
      <el-descriptions :column="1" border>
        <el-descriptions-item label="client_id">{{ issued.client_id }}</el-descriptions-item>
        <el-descriptions-item label="secret">
          <div class="secret-box">
            <code>{{ issued.secret }}</code>
            <el-button size="small" type="primary" link @click="copySecret">复制</el-button>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="名称">{{ issued.name }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button type="primary" @click="secretVisible = false">我已保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, Delete } from '@element-plus/icons-vue'
import { getClientList, createClient, revokeClient } from '@/api/harness'

const loading = ref(false)
const submitting = ref(false)
const tableData = ref([])
const createVisible = ref(false)
const secretVisible = ref(false)
const issued = ref({})
const formRef = ref(null)
const searchForm = reactive({ status: '' })
const pagination = reactive({ page: 1, pageSize: 20, total: 0 })
const form = reactive({ name: '', scopes: [], allowed_ips: [], expires_at: null, description: '' })
const rules = { name: [{ required: true, message: '请输入名称', trigger: 'blur' }] }

const fetchData = async () => {
  loading.value = true
  try {
    const params = { page: pagination.page, page_size: pagination.pageSize }
    if (searchForm.status) params.status = searchForm.status
    const res = await getClientList(params)
    tableData.value = res.data?.items || []
    pagination.total = res.data?.total || 0
  } finally {
    loading.value = false
  }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.status = ''; pagination.page = 1; fetchData() }

const openCreate = () => {
  Object.assign(form, { name: '', scopes: [], allowed_ips: [], expires_at: null, description: '' })
  createVisible.value = true
}

const handleCreate = async () => {
  await formRef.value.validate()
  submitting.value = true
  try {
    const payload = {
      name: form.name,
      scopes: form.scopes,
      allowed_ips: form.allowed_ips.length ? form.allowed_ips : null,
      expires_at: form.expires_at || null,
      description: form.description || null
    }
    const res = await createClient(payload)
    issued.value = res.data
    createVisible.value = false
    secretVisible.value = true
    fetchData()
  } finally {
    submitting.value = false
  }
}

const copySecret = async () => {
  try {
    await navigator.clipboard.writeText(issued.value.secret)
    ElMessage.success('已复制')
  } catch {
    ElMessage.warning('复制失败，请手动选择复制')
  }
}

const handleRevoke = async (row) => {
  await ElMessageBox.confirm(`确认吊销客户端 ${row.name}？吊销后无法恢复。`, '吊销凭据', { type: 'warning' })
  await revokeClient(row.client_id)
  ElMessage.success('已吊销')
  fetchData()
}

onMounted(fetchData)
</script>

<style scoped>
.harness-client { padding: 20px; }
.search-form { margin-bottom: 0; }
.pagination-wrapper { margin-top: 20px; display: flex; justify-content: flex-end; }
.secret-box { display: flex; align-items: center; gap: 12px; }
.secret-box code { word-break: break-all; background: #f5f7fa; padding: 4px 8px; border-radius: 4px; }
</style>
