<template>
  <div class="contact-list">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="关键词">
          <el-input v-model="searchForm.keyword" placeholder="姓名/手机号" clearable />
        </el-form-item>
        <el-form-item label="客户ID">
          <el-input-number v-model="searchForm.customer_id" :min="1" controls-position="right" style="width: 120px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>联系人列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新建联系人</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="name" label="姓名" min-width="120" />
        <el-table-column prop="customer_id" label="客户ID" width="90" align="center" />
        <el-table-column prop="phone" label="手机号" width="130" />
        <el-table-column prop="email" label="邮箱" min-width="160" />
        <el-table-column prop="position" label="职位" width="120" />
        <el-table-column prop="department" label="部门" width="120" />
        <el-table-column label="主联系人" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_primary" type="success" size="small">是</el-tag>
            <el-tag v-else type="info" size="small">否</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="240" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">编辑</el-button>
            <el-button v-if="!row.is_primary" type="success" link @click="handleSetPrimary(row)">设为主</el-button>
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑联系人' : '新建联系人'" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="客户ID" prop="customer_id">
          <el-input-number v-model="form.customer_id" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="请输入姓名" />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input v-model="form.phone" placeholder="请输入手机号" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="职位">
          <el-input v-model="form.position" placeholder="请输入职位" />
        </el-form-item>
        <el-form-item label="部门">
          <el-input v-model="form.department" placeholder="请输入部门" />
        </el-form-item>
        <el-form-item label="主联系人">
          <el-switch v-model="form.is_primary" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
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
import { getContactList, createContact, updateContact, deleteContact, setPrimaryContact } from '@/api/crm'

const loading = ref(false)
const submitting = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const searchForm = reactive({ keyword: '', customer_id: null })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const form = reactive({
  id: null, customer_id: null, name: '', phone: '', email: '',
  position: '', department: '', is_primary: false, remark: ''
})

const rules = {
  customer_id: [{ required: true, message: '请输入客户ID', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getContactList({ page: pagination.page, page_size: pagination.pageSize, ...searchForm })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) { console.error('获取联系人列表失败:', e) }
  finally { loading.value = false }
}

const resetForm = () => {
  form.id = null; form.customer_id = null; form.name = ''; form.phone = ''; form.email = ''
  form.position = ''; form.department = ''; form.is_primary = false; form.remark = ''
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.keyword = ''; searchForm.customer_id = null; handleSearch() }
const handleAdd = () => { isEdit.value = false; resetForm(); dialogVisible.value = true }
const handleEdit = (row) => { isEdit.value = true; Object.assign(form, row); dialogVisible.value = true }

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    submitting.value = true
    const data = {
      customer_id: form.customer_id, name: form.name, phone: form.phone || null,
      email: form.email || null, position: form.position || null, department: form.department || null,
      is_primary: form.is_primary, remark: form.remark || null
    }
    if (isEdit.value) { await updateContact(form.id, data); ElMessage.success('更新成功') }
    else { await createContact(data); ElMessage.success('创建成功') }
    dialogVisible.value = false; fetchData()
  } catch (e) { if (e !== false) ElMessage.error(e.message || '操作失败') }
  finally { submitting.value = false }
}

const handleSetPrimary = async (row) => {
  try {
    await setPrimaryContact(row.id)
    ElMessage.success('设置成功'); fetchData()
  } catch (e) { ElMessage.error(e.message || '操作失败') }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除联系人 "${row.name}" 吗？`, '提示', { type: 'warning' })
    await deleteContact(row.id); ElMessage.success('删除成功'); fetchData()
  } catch (e) {}
}

onMounted(() => { fetchData() })
</script>

<style lang="scss" scoped>
.contact-list {
  .search-card { margin-bottom: 16px; }
  .table-card { .card-header { display: flex; justify-content: space-between; align-items: center; } }
  .pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
}
</style>
