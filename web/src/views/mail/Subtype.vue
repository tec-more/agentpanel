<template>
  <div class="mail-subtype">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="关键字">
          <el-input v-model="searchForm.keyword" placeholder="名称/编码" clearable />
        </el-form-item>
        <el-form-item label="适用模型">
          <el-input v-model="searchForm.model" placeholder="如 purchase_order" clearable />
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
          <el-button type="success" :icon="Plus" @click="handleAdd">新建子类型</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <span>消息子类型</span>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="code" label="编码" width="220" show-overflow-tooltip />
        <el-table-column prop="name" label="名称" width="180" />
        <el-table-column label="适用模型" width="160">
          <template #default="{ row }">{{ row.model || '通用' }}</template>
        </el-table-column>
        <el-table-column label="默认评论" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.default" size="small" type="success">是</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="内部" width="70" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.internal" size="small" type="warning">是</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="sequence" label="排序" width="70" align="center" />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="系统" width="70" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_system" size="small" type="danger">是</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">编辑</el-button>
            <el-button
              type="danger"
              link
              :icon="Delete"
              :disabled="row.is_system"
              @click="handleDelete(row)"
            >删除</el-button>
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑子类型' : '新建子类型'" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如 评论" />
        </el-form-item>
        <el-form-item label="编码" prop="code">
          <el-input
            v-model="form.code"
            placeholder="如 mt_comment"
            :disabled="isEdit"
          />
          <div class="form-tip">编码唯一，创建后不可修改</div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="适用模型">
          <el-input v-model="form.model" placeholder="留空表示通用" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sequence" :min="0" :max="9999" />
        </el-form-item>
        <el-form-item label="选项">
          <el-checkbox v-model="form.is_active">启用</el-checkbox>
          <el-checkbox v-model="form.default">评论默认</el-checkbox>
          <el-checkbox v-model="form.internal">仅内部可见</el-checkbox>
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
import { listSubtypes, createSubtype, updateSubtype, deleteSubtype } from '@/api/mail'

const loading = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const formRef = ref(null)

const searchForm = reactive({
  keyword: '',
  model: '',
  is_active: null
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const form = reactive({
  id: null,
  name: '',
  code: '',
  description: '',
  model: '',
  sequence: 10,
  is_active: true,
  default: false,
  internal: false
})

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize
    }
    if (searchForm.keyword) params.keyword = searchForm.keyword
    if (searchForm.model) params.model = searchForm.model
    if (searchForm.is_active !== null && searchForm.is_active !== '') {
      params.is_active = searchForm.is_active
    }
    const res = await listSubtypes(params)
    tableData.value = res.data?.items || []
    pagination.total = res.data?.total || 0
  } catch (e) {
    console.error('获取子类型失败', e)
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
  searchForm.model = ''
  searchForm.is_active = null
  pagination.page = 1
  fetchData()
}

const resetForm = () => {
  Object.assign(form, {
    id: null,
    name: '',
    code: '',
    description: '',
    model: '',
    sequence: 10,
    is_active: true,
    default: false,
    internal: false
  })
}

const handleAdd = () => {
  resetForm()
  isEdit.value = false
  dialogVisible.value = true
}

const handleEdit = (row) => {
  Object.assign(form, {
    id: row.id,
    name: row.name,
    code: row.code,
    description: row.description || '',
    model: row.model || '',
    sequence: row.sequence,
    is_active: row.is_active,
    default: row.default,
    internal: row.internal
  })
  isEdit.value = true
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    submitting.value = true
    try {
      const payload = {
        name: form.name,
        code: form.code,
        description: form.description || null,
        model: form.model || null,
        sequence: form.sequence,
        is_active: form.is_active,
        default: form.default,
        internal: form.internal
      }
      if (isEdit.value) {
        await updateSubtype(form.id, payload)
        ElMessage.success('更新成功')
      } else {
        await createSubtype(payload)
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
  ElMessageBox.confirm(`确认删除子类型「${row.name}」？`, '提示', {
    type: 'warning'
  }).then(async () => {
    try {
      await deleteSubtype(row.id)
      ElMessage.success('删除成功')
      fetchData()
    } catch (e) {
      // 拦截器已提示
    }
  }).catch(() => {})
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.mail-subtype {
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
