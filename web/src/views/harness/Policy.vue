<template>
  <div class="harness-policy">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="全部" clearable style="width: 130px">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="disabled" />
            <el-option label="全部" value="all" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button type="success" :icon="Plus" @click="openCreate">新建策略</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>动作策略（fail-closed：未匹配即拒绝）</span>
          <el-tag size="small" type="info">审批插件未启用时 approve 一律降级为 deny</el-tag>
        </div>
      </template>
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="priority" label="优先级" width="80" align="center" />
        <el-table-column prop="code" label="编码" width="150" />
        <el-table-column prop="name" label="名称" width="150" />
        <el-table-column prop="action_pattern" label="动作模式" width="170" />
        <el-table-column label="效果" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="effectTagType(row.effect)">{{ row.effect }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="风险" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="riskTagType(row.risk_level)">{{ row.risk_level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="需审批" width="80" align="center">
          <template #default="{ row }">{{ row.require_approval ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80" align="center" />
        <el-table-column label="条件" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.conditions ? JSON.stringify(row.conditions) : '-' }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" style="margin-top: 12px">
      <template #header>
        <div class="card-header">
          <span>运行时权限状态（permission preset / sandbox mode / approval policy）</span>
          <el-button size="small" :icon="Refresh" @click="fetchPresetStates">刷新</el-button>
        </div>
      </template>
      <el-table v-loading="presetLoading" :data="presetStates" size="small" border stripe max-height="360">
        <el-table-column prop="occurred_at" label="时间" width="175" />
        <el-table-column prop="action" label="状态类型" width="150" />
        <el-table-column prop="run_no" label="运行号" width="200" show-overflow-tooltip />
        <el-table-column prop="raw_seq" label="原始序号" width="90" align="center" />
        <el-table-column label="取值" min-width="260">
          <template #default="{ row }">{{ JSON.stringify(row.detail) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createVisible" title="新建动作策略" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" placeholder="如 deny_git_push" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="策略名称" />
        </el-form-item>
        <el-form-item label="动作模式" prop="action_pattern">
          <el-input v-model="form.action_pattern" placeholder="支持通配符，如 tool.git.* / tool.shell" />
        </el-form-item>
        <el-form-item label="效果">
          <el-select v-model="form.effect" style="width: 100%">
            <el-option label="allow（放行）" value="allow" />
            <el-option label="deny（拒绝）" value="deny" />
            <el-option label="approve（需审批）" value="approve" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险等级">
          <el-select v-model="form.risk_level" style="width: 100%">
            <el-option label="low" value="low" />
            <el-option label="medium" value="medium" />
            <el-option label="high" value="high" />
            <el-option label="critical" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="1" :max="9999" />
        </el-form-item>
        <el-form-item label="条件(JSON)">
          <el-input v-model="form.conditionsText" type="textarea" :rows="3" placeholder='如 {"path_prefix": "/etc"}' />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Plus, Refresh } from '@element-plus/icons-vue'
import { getPolicyList, createPolicy, getAuditEvents } from '@/api/harness'

const loading = ref(false)
const submitting = ref(false)
const presetLoading = ref(false)
const tableData = ref([])
const presetStates = ref([])
const createVisible = ref(false)
const formRef = ref(null)
const searchForm = reactive({ status: 'active' })
const form = reactive({
  code: '', name: '', action_pattern: '', effect: 'deny', risk_level: 'high',
  priority: 100, conditionsText: '', description: ''
})
const rules = {
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  action_pattern: [{ required: true, message: '请输入动作模式', trigger: 'blur' }]
}

const effectTagType = (effect) => {
  if (effect === 'allow') return 'success'
  if (effect === 'deny') return 'danger'
  if (effect === 'approve') return 'warning'
  return 'info'
}
const riskTagType = (level) => {
  if (level === 'critical') return 'danger'
  if (level === 'high') return 'warning'
  if (level === 'medium') return 'primary'
  return 'info'
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getPolicyList({ status: searchForm.status, page: 1, page_size: 200 })
    tableData.value = res.data?.items || []
  } finally {
    loading.value = false
  }
}

const fetchPresetStates = async () => {
  presetLoading.value = true
  try {
    const actions = ['permission.preset', 'sandbox.mode', 'approval.policy']
    const results = await Promise.all(
      actions.map((action) => getAuditEvents({ action, page: 1, page_size: 50 }))
    )
    presetStates.value = results
      .flatMap((res) => res.data?.items || [])
      .sort((a, b) => (b.occurred_at || '').localeCompare(a.occurred_at || ''))
      .slice(0, 100)
  } finally {
    presetLoading.value = false
  }
}

const handleSearch = () => fetchData()

const openCreate = () => {
  Object.assign(form, {
    code: '', name: '', action_pattern: '', effect: 'deny', risk_level: 'high',
    priority: 100, conditionsText: '', description: ''
  })
  createVisible.value = true
}

const handleCreate = async () => {
  await formRef.value.validate()
  let conditions = null
  if (form.conditionsText.trim()) {
    try {
      conditions = JSON.parse(form.conditionsText)
    } catch {
      ElMessage.error('条件不是合法 JSON')
      return
    }
  }
  submitting.value = true
  try {
    await createPolicy({
      code: form.code,
      name: form.name,
      action_pattern: form.action_pattern,
      effect: form.effect,
      risk_level: form.risk_level,
      priority: form.priority,
      conditions,
      status: 'active',
      description: form.description || null
    })
    ElMessage.success('策略已创建')
    createVisible.value = false
    fetchData()
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  fetchData()
  fetchPresetStates()
})
</script>

<style scoped>
.harness-policy { padding: 20px; }
.search-form { margin-bottom: 0; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
</style>

