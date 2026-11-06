<template>
  <div class="account-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>会计科目</span>
        </div>
      </template>
      
      <div class="search-row">
        <el-form :inline="true" :model="searchForm" class="search-form">
          <el-form-item label="搜索">
            <el-input v-model="searchForm.keyword" placeholder="搜索科目名称或编码" clearable />
          </el-form-item>
          <el-form-item label="科目类型">
            <el-select v-model="searchForm.account_type" placeholder="全部类型" clearable style="width: 140px">
              <el-option v-for="type in accountTypes" :key="type.value" :label="type.label" :value="type.value" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
        <div class="search-actions">
          <el-button @click="handleAdd" type="primary">新增科目</el-button>
        </div>
      </div>
    </el-card>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="code" label="科目编码" />
        <el-table-column prop="name" label="科目名称" />
        <el-table-column prop="account_type" label="科目类型">
          <template #default="{ row }">
            {{ getAccountTypeName(row.account_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="parent_name" label="上级科目" />
        <el-table-column prop="balance" label="余额" />
        <el-table-column prop="is_active" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
              <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>
    
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form ref="formRef" :model="formData" :rules="rules" label-width="100px">
        <el-form-item label="科目编码" prop="code">
          <el-input v-model="formData.code" placeholder="请输入科目编码" />
        </el-form-item>
        <el-form-item label="科目名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入科目名称" />
        </el-form-item>
        <el-form-item label="科目类型" prop="account_type">
          <el-select v-model="formData.account_type" placeholder="请选择科目类型">
            <el-option v-for="type in accountTypes" :key="type.value" :label="type.label" :value="type.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="上级科目">
          <el-select v-model="formData.parent_id" placeholder="请选择上级科目" clearable>
            <el-option v-for="acc in accountList" :key="acc.id" :label="acc.code + ' ' + acc.name" :value="acc.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="formData.description" type="textarea" placeholder="请输入备注" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import request from '@/utils/request'

const tableData = ref([])
const accountTypes = ref([])
const accountList = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增科目')
const isEdit = ref(false)
const currentId = ref(null)
const loading = ref(false)

const searchForm = reactive({
  keyword: '',
  account_type: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const formData = reactive({
  code: '',
  name: '',
  account_type: '',
  parent_id: null,
  description: ''
})

const rules = {
  code: [{ required: true, message: '请输入科目编码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入科目名称', trigger: 'blur' }],
  account_type: [{ required: true, message: '请选择科目类型', trigger: 'change' }]
}

const getAccountTypeName = (type) => {
  const found = accountTypes.value.find(t => t.value === type)
  return found ? found.label : type
}

const handleSearch = async () => {
  pagination.page = 1
  await fetchData()
}

const handleReset = () => {
  searchForm.keyword = ''
  searchForm.account_type = ''
  handleSearch()
}

const handleAdd = () => {
  isEdit.value = false
  currentId.value = null
  dialogTitle.value = '新增科目'
  Object.assign(formData, {
    code: '',
    name: '',
    account_type: '',
    parent_id: null,
    description: ''
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  currentId.value = row.id
  dialogTitle.value = '编辑科目'
  Object.assign(formData, {
    code: row.code,
    name: row.name,
    account_type: row.account_type,
    parent_id: row.parent_id,
    description: row.description || ''
  })
  dialogVisible.value = true
}

const handleDelete = async (row) => {
  await ElMessageBox.confirm(
    `确定删除科目 ${row.name} 吗？`,
    '提示',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )
  const data = await request.delete(`/v1/finance/accounts/${row.id}`)
  if (data.code === 0) {
    ElMessage.success(data.msg)
    fetchData()
  } else {
    ElMessage.error(data.msg || '删除失败')
  }
}

const handleSave = async () => {
  if (!formData.code || !formData.name || !formData.account_type) {
    ElMessage.warning('请填写必填项')
    return
  }
  
  if (isEdit.value) {
    const data = await request.put(`/v1/finance/accounts/${currentId.value}`, formData)
    if (data.code === 0) {
      ElMessage.success('保存成功')
      dialogVisible.value = false
      fetchData()
    } else {
      ElMessage.error(data.msg || '保存失败')
    }
  } else {
    const data = await request.post('/v1/finance/accounts/', formData)
    if (data.code === 0) {
      ElMessage.success('保存成功')
      dialogVisible.value = false
      fetchData()
    } else {
      ElMessage.error(data.msg || '保存失败')
    }
  }
}

const loadAccountTypes = async () => {
  const data = await request.get('/v1/finance/accounts/types')
  if (data.code === 0) {
    accountTypes.value = data.data
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/finance/accounts/', { params: { page: pagination.page, page_size: pagination.page_size, keyword: searchForm.keyword, account_type: searchForm.account_type } })
    tableData.value = data.data?.data || []
    pagination.total = data.data?.total || 0
    pagination.page = data.data?.page || 1
    pagination.page_size = data.data?.page_size || 20
  } catch (error) {
    tableData.value = []
    pagination.total = 0
  }
  loading.value = false
}

const fetchAccountList = async () => {
  const data = await request.get('/v1/finance/accounts/', { params: { page_size: 100 } })
  accountList.value = data.data?.data || []
}

onMounted(() => {
  loadAccountTypes()
  fetchData()
  fetchAccountList()
})
</script>

<style lang="scss" scoped>
.account-index {
  padding: 20px;
  
  .search-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    flex-wrap: wrap;
    gap: 10px;
    
    .search-form {
      flex: 1;
      margin: 0;
    }
    
    .search-actions {
      flex-shrink: 0;
    }
  }
}
</style>


