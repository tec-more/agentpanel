<template>
  <div class="mail-mapping">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="业务表名">
          <el-input v-model="searchForm.model" placeholder="如 purchase_order" clearable />
        </el-form-item>
        <el-form-item label="动作">
          <el-select v-model="searchForm.action" placeholder="全部" clearable style="width: 120px">
            <el-option label="创建" value="create" />
            <el-option label="更新" value="update" />
            <el-option label="删除" value="delete" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.is_active" placeholder="全部" clearable style="width: 120px">
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
          <el-button type="success" :icon="Plus" @click="handleAdd">新建映射</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <span>事件→消息映射</span>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="model" label="业务表名" width="170" />
        <el-table-column label="动作" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="actionTagType(row.action)">{{ actionLabel(row.action) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="子类型" width="180">
          <template #default="{ row }">{{ row.subtype?.name || `#${row.subtype_id}` }}</template>
        </el-table-column>
        <el-table-column label="条件字段" width="130">
          <template #default="{ row }">{{ row.condition_field || '-' }}</template>
        </el-table-column>
        <el-table-column label="条件值" width="120">
          <template #default="{ row }">{{ row.condition_value || '-' }}</template>
        </el-table-column>
        <el-table-column label="通知关注者" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.notify_followers ? 'success' : 'info'" size="small">
              {{ row.notify_followers ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="通知创建者" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.notify_creator ? 'success' : 'info'" size="small">
              {{ row.notify_creator ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="name_template" label="主题模板" min-width="180" show-overflow-tooltip />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑映射' : '新建映射'" width="640px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="业务表名" prop="model">
          <el-input v-model="form.model" placeholder="如 purchase_order" />
        </el-form-item>
        <el-form-item label="动作" prop="action">
          <el-select v-model="form.action" placeholder="请选择" style="width: 100%">
            <el-option label="创建 create" value="create" />
            <el-option label="更新 update" value="update" />
            <el-option label="删除 delete" value="delete" />
          </el-select>
        </el-form-item>
        <el-form-item label="子类型" prop="subtype_id">
          <el-select v-model="form.subtype_id" placeholder="请选择" filterable style="width: 100%">
            <el-option
              v-for="s in subtypeOptions"
              :key="s.id"
              :label="`${s.name} (${s.code})`"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="条件字段">
          <el-input v-model="form.condition_field" placeholder="如 status（仅 update 时生效）" />
        </el-form-item>
        <el-form-item label="条件值">
          <el-input v-model="form.condition_value" placeholder="如 approved" />
        </el-form-item>
        <el-form-item label="主题模板">
          <el-input v-model="form.name_template" placeholder="如 采购订单 #{record_id} 已创建" />
          <div class="form-tip">支持占位符 {record_id}、{field_name}、{old_field_name}、{record_name}</div>
        </el-form-item>
        <el-form-item label="正文模板">
          <el-input v-model="form.body_template" type="textarea" :rows="3" />
          <div class="form-tip">支持占位符 {record_id}、{field_name}、{old_field_name}、{record_name}</div>
        </el-form-item>
        <el-form-item label="通知选项">
          <el-checkbox v-model="form.is_active">启用</el-checkbox>
          <el-checkbox v-model="form.notify_followers">通知关注者</el-checkbox>
          <el-checkbox v-model="form.notify_creator">通知记录创建者</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, Edit, Delete } from '@element-plus/icons-vue'
import { listMappings, createMapping, updateMapping, deleteMapping, listSubtypes } from '@/api/mail'

const loading = ref(false)
const tableData = ref([])
const subtypeOptions = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref(null)

const searchForm = reactive({
  model: '',
  action: '',
  is_active: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = reactive({
  id: null,
  model: '',
  action: '',
  subtype_id: null,
  condition_field: '',
  condition_value: '',
  name_template: '',
  body_template: '',
  is_active: true,
  notify_followers: true,
  notify_creator: false
})

const rules = {
  model: [{ required: true, message: '请输入业务表名', trigger: 'blur' }],
  action: [{ required: true, message: '请选择动作', trigger: 'change' }],
  subtype_id: [{ required: true, message: '请选择子类型', trigger: 'change' }]
}

const actionTagType = (a) => {
  if (a === 'create') return 'success'
  if (a === 'update') return 'warning'
  if (a === 'delete') return 'danger'
  return 'info'
}

const actionLabel = (a) => {
  if (a === 'create') return '创建'
  if (a === 'update') return '更新'
  if (a === 'delete') return '删除'
  return a
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (searchForm.model) params.model = searchForm.model
    if (searchForm.action) params.action = searchForm.action
    if (searchForm.is_active !== null && searchForm.is_active !== '') {
      params.is_active = searchForm.is_active
    }
    const res = await listMappings(params)
    tableData.value = res.data?.items || []
    pagination.total = res.data?.total || 0
  } catch (e) {
    console.error('获取映射失败', e)
  } finally {
    loading.value = false
  }
}

const fetchSubtypes = async () => {
  try {
    const res = await listSubtypes({ page: 1, page_size: 200, is_active: true })
    subtypeOptions.value = res.data?.items || []
  } catch (e) {
    console.error('获取子类型选项失败', e)
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.model = ''
  searchForm.action = ''
  searchForm.is_active = null
  pagination.page = 1
  fetchData()
}

const resetForm = () => {
  Object.assign(form, {
    id: null,
    model: '',
    action: '',
    subtype_id: null,
    condition_field: '',
    condition_value: '',
    name_template: '',
    body_template: '',
    is_active: true,
    notify_followers: true,
    notify_creator: false
  })
}

const handleAdd = () => {
  resetForm()
  isEdit.value = false
  dialogVisible.value = true
  if (!subtypeOptions.value.length) fetchSubtypes()
}

const handleEdit = (row) => {
  Object.assign(form, {
    id: row.id,
    model: row.model,
    action: row.action,
    subtype_id: row.subtype_id,
    condition_field: row.condition_field || '',
    condition_value: row.condition_value || '',
    name_template: row.name_template || '',
    body_template: row.body_template || '',
    is_active: row.is_active,
    notify_followers: row.notify_followers,
    notify_creator: row.notify_creator
  })
  isEdit.value = true
  dialogVisible.value = true
  if (!subtypeOptions.value.length) fetchSubtypes()
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload = {
        model: form.model,
        action: form.action,
        subtype_id: form.subtype_id,
        condition_field: form.condition_field || null,
        condition_value: form.condition_value || null,
        name_template: form.name_template || null,
        body_template: form.body_template || null,
        is_active: form.is_active,
        notify_followers: form.notify_followers,
        notify_creator: form.notify_creator
      }
      if (isEdit.value) {
        await updateMapping(form.id, payload)
        ElMessage.success('更新成功')
      } else {
        await createMapping(payload)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      fetchData()
    } catch (e) {
      // 拦截器已提示
    } finally {
      submitting.value = false
    }
  })
}

const handleDelete = (row) => {
  ElMessageBox.confirm(`确认删除映射「${row.model}/${row.action}」？`, '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      await deleteMapping(row.id)
      ElMessage.success('删除成功')
      fetchData()
    } catch (e) {
      // 拦截器已提示
    }
  }).catch(() => {})
}

onMounted(() => {
  fetchData()
  fetchSubtypes()
})
</script>

<style scoped>
.mail-mapping {
  padding: 16px;
}
.search-card {
  margin-bottom: 16px;
}
.pagination-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.form-tip {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}
</style>
