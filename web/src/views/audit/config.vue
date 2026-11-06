<template>
  <div class="audit-config">
    <!-- 搜索栏 -->
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="模块名">
          <el-input v-model="searchForm.module_name" placeholder="请输入模块名" clearable />
        </el-form-item>
        <el-form-item label="显示名称">
          <el-input v-model="searchForm.display_name" placeholder="请输入显示名称" clearable />
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
          <span>审计配置列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新增配置</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="module_name" label="模块名" width="200" />
        <el-table-column prop="display_name" label="显示名称" width="200" />
        <el-table-column label="是否启用" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.enabled ? 'success' : 'info'">
              {{ row.enabled ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="log_create" label="记录创建" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.log_create ? 'success' : 'info'">
              {{ row.log_create ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="log_update" label="记录更新" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.log_update ? 'success' : 'info'">
              {{ row.log_update ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="log_delete" label="记录删除" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.log_delete ? 'success' : 'info'">
              {{ row.log_delete ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="log_query" label="记录查询" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.log_query ? 'success' : 'info'">
              {{ row.log_query ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="retention_days" label="保留天数" width="100" align="center" />
        <el-table-column label="是否启警告" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.alert_enabled ? 'warning' : 'info'">
              {{ row.alert_enabled ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link :icon="View" @click="handleDetail(row)">详情</el-button>
              <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">编辑</el-button>
              <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
            </div>
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
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑审计配置' : '新增审计配置'"
      width="700px"
      @close="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-form-item label="模块名" prop="module_name">
          <el-input v-model="form.module_name" :disabled="isEdit" placeholder="请输入模块名" />
        </el-form-item>
        <el-form-item label="显示名称" prop="display_name">
          <el-input v-model="form.display_name" placeholder="请输入显示名称" />
        </el-form-item>
        <el-form-item label="是否启用">
          <el-radio-group v-model="form.enabled">
            <el-radio :value="true">是</el-radio>
            <el-radio :value="false">否</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="记录操作">
          <el-checkbox v-model="form.log_create">创建</el-checkbox>
          <el-checkbox v-model="form.log_update">更新</el-checkbox>
          <el-checkbox v-model="form.log_delete">删除</el-checkbox>
          <el-checkbox v-model="form.log_query">查询</el-checkbox>
        </el-form-item>
        <el-form-item label="敏感字段">
          <el-tag
            v-for="(field, index) in form.sensitive_fields"
            :key="index"
            closable
            @close="handleRemoveSensitiveField(index)"
            style="margin-right: 8px; margin-bottom: 8px;"
          >
            {{ field }}
          </el-tag>
          <div style="margin-top: 8px;">
            <el-input v-model="newSensitiveField" placeholder="请输入字段名" style="width: 200px; margin-right: 8px;" />
            <el-button type="primary" @click="handleAddSensitiveField">添加</el-button>
          </div>
        </el-form-item>
        <el-form-item label="排除路径">
          <el-tag
            v-for="(path, index) in form.exclude_paths"
            :key="index"
            closable
            @close="handleRemoveExcludePath(index)"
            style="margin-right: 8px; margin-bottom: 8px;"
          >
            {{ path }}
          </el-tag>
          <div style="margin-top: 8px;">
            <el-input v-model="newExcludePath" placeholder="请输入路径" style="width: 200px; margin-right: 8px;" />
            <el-button type="primary" @click="handleAddExcludePath">添加</el-button>
          </div>
        </el-form-item>
        <el-form-item label="保留天数">
          <el-input-number v-model="form.retention_days" :min="1" :max="3650" />
        </el-form-item>
        <el-form-item label="是否启警告">
          <el-radio-group v-model="form.alert_enabled">
            <el-radio :value="true">是</el-radio>
            <el-radio :value="false">否</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="警告规则">
          <el-input
            v-model="alertRulesStr"
            type="textarea"
            :rows="4"
            placeholder='请输入警告规则(JSON格式)，例如：{"threshold": 100}'
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="3" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, View, Edit, Delete } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const submitLoading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const tableData = ref([])
const newSensitiveField = ref('')
const newExcludePath = ref('')

const searchForm = reactive({
  module_name: '',
  display_name: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const form = ref({
  module_name: '',
  display_name: '',
  enabled: true,
  log_create: true,
  log_update: true,
  log_delete: true,
  log_query: false,
  sensitive_fields: [],
  exclude_paths: [],
  retention_days: 90,
  alert_enabled: false,
  alert_rules: null,
  remark: ''
})

const alertRulesStr = computed({
  get: () => form.value.alert_rules ? JSON.stringify(form.value.alert_rules, null, 2) : '',
  set: (val) => {
    try {
      form.value.alert_rules = val ? JSON.parse(val) : null
    } catch {
      form.value.alert_rules = null
    }
  }
})

const rules = {
  module_name: [{ required: true, message: '请输入模块名', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入显示名称', trigger: 'blur' }]
}

const createAuditConfig = async (data) => {
  return request.post('/v1/audit/audit-configs', data)
}

const updateAuditConfig = async (id, data) => {
  return request.put(`/v1/audit/audit-configs/${id}`, data)
}

const deleteAuditConfig = async (id) => {
  return request.delete(`/v1/audit/audit-configs/${id}`)
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      ...searchForm
    }
    const res = await request.get('/v1/audit/audit-configs/list', { params })
    tableData.value = res.data.items || res.data || []
    pagination.total = tableData.value.length
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
  searchForm.module_name = ''
  searchForm.display_name = ''
  handleSearch()
}

const handleAdd = () => {
  isEdit.value = false
  form.value = {
    module_name: '',
    display_name: '',
    enabled: true,
    log_create: true,
    log_update: true,
    log_delete: true,
    log_query: false,
    sensitive_fields: [],
    exclude_paths: [],
    retention_days: 90,
    alert_enabled: false,
    alert_rules: null,
    remark: ''
  }
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  form.value = {
    module_name: row.module_name,
    display_name: row.display_name,
    enabled: row.enabled,
    log_create: row.log_create,
    log_update: row.log_update,
    log_delete: row.log_delete,
    log_query: row.log_query,
    sensitive_fields: row.sensitive_fields || [],
    exclude_paths: row.exclude_paths || [],
    retention_days: row.retention_days,
    alert_enabled: row.alert_enabled,
    alert_rules: row.alert_rules,
    remark: row.remark || ''
  }
  dialogVisible.value = true
}

const handleDetail = (row) => {
  ElMessageBox.alert(
    `
    <pre style="text-align: left;">
${JSON.stringify(row, null, 2)}
    </pre>
    `,
    '配置详情',
    {
      dangerouslyUseHTMLString: true
    }
  )
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除该配置吗？', '提示', { type: 'warning' })
    await deleteAuditConfig(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    // 取消或错误
  }
}

const handleAddSensitiveField = () => {
  if (newSensitiveField.value && !form.value.sensitive_fields.includes(newSensitiveField.value)) {
    form.value.sensitive_fields.push(newSensitiveField.value)
    newSensitiveField.value = ''
  }
}

const handleRemoveSensitiveField = (index) => {
  form.value.sensitive_fields.splice(index, 1)
}

const handleAddExcludePath = () => {
  if (newExcludePath.value && !form.value.exclude_paths.includes(newExcludePath.value)) {
    form.value.exclude_paths.push(newExcludePath.value)
    newExcludePath.value = ''
  }
}

const handleRemoveExcludePath = (index) => {
  form.value.exclude_paths.splice(index, 1)
}

const handleSubmit = async () => {
  await formRef.value.validate()
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateAuditConfig(form.value.id, form.value)
      ElMessage.success('更新成功')
    } else {
      await createAuditConfig(form.value)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    // 错误已处理
  } finally {
    submitLoading.value = false
  }
}

const resetForm = () => {
  formRef.value?.resetFields()
}

fetchData()
</script>

<style lang="scss" scoped>
.audit-config {
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
    }
  }

  .pagination-wrapper {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }

  .action-buttons {
    display: flex;
    justify-content: flex-start;
    align-items: center;
    gap: 4px;
  }
}
</style>


