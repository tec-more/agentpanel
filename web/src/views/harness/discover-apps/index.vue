<template>
  <div class="discover-apps-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>应用配置</span>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            新增应用
          </el-button>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="这里配置 dsh 客户端「发现应用」面板中展示的应用。 portal 类型会用客户账号的一次性票据免登进入客户门户；link 类型直接用系统浏览器打开外部地址。 只有启用的应用会下发给客户端。"
        class="tips"
      />

      <el-table :data="tableData" v-loading="loading" border style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column label="应用" min-width="200">
          <template #default="{ row }">
            <div class="app-cell">
              <span class="app-icon" :style="iconStyle(row)">{{ row.icon_text || 'AP' }}</span>
              <span>
                <div class="app-name">{{ row.name }}</div>
                <div class="app-desc">{{ row.description || '-' }}</div>
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="打开方式" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.open_mode === 'portal' ? 'primary' : 'info'" size="small">
              {{ row.open_mode === 'portal' ? '门户免登' : '外部链接' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target" label="跳转目标" min-width="180" show-overflow-tooltip />
        <el-table-column prop="sort" label="排序" width="80" align="center" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_active"
              @change="(value) => handleToggle(row, value)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无应用，点击右上角新增" />
        </template>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑应用' : '新增应用'" width="520px">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="应用名称" prop="name">
          <el-input v-model="form.name" maxlength="64" placeholder="如：AgentPanel" />
        </el-form-item>
        <el-form-item label="卡片描述" prop="description">
          <el-input v-model="form.description" maxlength="160" placeholder="一句话说明，如：后台管理 · 业务支撑" />
        </el-form-item>
        <el-form-item label="图标文字" prop="icon_text">
          <el-input v-model="form.icon_text" maxlength="4" placeholder="1-4 个字符，如 AP" />
        </el-form-item>
        <el-form-item label="图标颜色" prop="icon_color">
          <el-color-picker v-model="form.icon_color" />
          <span class="form-hint">留空使用客户端主题默认色</span>
        </el-form-item>
        <el-form-item label="打开方式" prop="open_mode">
          <el-select v-model="form.open_mode" style="width: 100%">
            <el-option label="门户免登（portal）" value="portal" />
            <el-option label="外部链接（link）" value="link" />
          </el-select>
        </el-form-item>
        <el-form-item label="跳转目标" prop="target">
          <el-input v-model="form.target" maxlength="512" :placeholder="form.open_mode === 'portal' ? '站内路径，如 /dashboard' : 'https:// 开头的完整地址'" />
          <div class="form-hint">
            {{ form.open_mode === 'portal'
              ? '以 / 开头的站内路径，例如 /dashboard；客户端会用一次性票据免登。'
              : '仅允许 https 地址，或本机 http 地址（127.0.0.1 / localhost）。' }}
          </div>
        </el-form-item>
        <el-form-item label="排序" prop="sort">
          <el-input-number v-model="form.sort" :min="-1000" :max="10000" />
          <span class="form-hint">数值越小越靠前</span>
        </el-form-item>
        <el-form-item label="启用" prop="is_active">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createDiscoverApp,
  deleteDiscoverApp,
  getDiscoverApps,
  toggleDiscoverApp,
  updateDiscoverApp,
} from '@/api/discoverApp'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const tableData = ref([])
const formRef = ref(null)

const emptyForm = () => ({
  name: '',
  description: '',
  icon_text: '',
  icon_color: null,
  open_mode: 'portal',
  target: '/dashboard',
  sort: 0,
  is_active: true,
})
const form = reactive(emptyForm())

const rules = {
  name: [{ required: true, message: '请输入应用名称', trigger: 'blur' }],
  target: [
    { required: true, message: '请输入跳转目标', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (form.open_mode === 'portal') {
          if (!value.startsWith('/') || value.startsWith('//')) return callback(new Error('站内路径需以 / 开头且不能是 //'))
        } else {
          try {
            const url = new URL(value)
            const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)
            if (url.username || url.password || !(url.protocol === 'https:' || (loopback && url.protocol === 'http:'))) {
              return callback(new Error('仅允许 https 或本机 http 地址'))
            }
          } catch {
            return callback(new Error('请输入完整合法的 URL'))
          }
        }
        callback()
      },
      trigger: 'blur',
    },
  ],
}

const iconStyle = (row) => (row.icon_color ? { background: row.icon_color } : {})

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getDiscoverApps()
    tableData.value = res.data?.items || []
  } finally {
    loading.value = false
  }
}

const handleCreate = () => {
  editingId.value = null
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

const handleEdit = (row) => {
  editingId.value = row.id
  Object.assign(form, emptyForm(), {
    name: row.name,
    description: row.description || '',
    icon_text: row.icon_text || '',
    icon_color: row.icon_color || null,
    open_mode: row.open_mode,
    target: row.target,
    sort: row.sort,
    is_active: row.is_active,
  })
  dialogVisible.value = true
}

const handleSave = async () => {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  saving.value = true
  try {
    const payload = { ...form, icon_color: form.icon_color || null }
    if (editingId.value) await updateDiscoverApp(editingId.value, payload)
    else await createDiscoverApp(payload)
    ElMessage.success('保存成功')
    dialogVisible.value = false
    await fetchData()
  } finally {
    saving.value = false
  }
}

const handleToggle = async (row, value) => {
  try {
    await toggleDiscoverApp(row.id, value)
    row.is_active = value
    ElMessage.success(value ? '已启用' : '已停用')
  } catch {
    await fetchData()
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除应用「${row.name}」吗？`, '提示', { type: 'warning' })
  } catch {
    return
  }
  await deleteDiscoverApp(row.id)
  ElMessage.success('删除成功')
  await fetchData()
}

onMounted(fetchData)
</script>

<style scoped>
.discover-apps-container { padding: 20px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.tips { margin-bottom: 16px; }
.app-cell { display: flex; align-items: center; gap: 10px; }
.app-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: #409eff;
  color: #fff;
  font-size: 11px;
  flex-shrink: 0;
}
.app-name { font-size: 13px; }
.app-desc { font-size: 11px; color: #909399; }
.form-hint { margin-left: 10px; font-size: 12px; color: #909399; }
</style>
