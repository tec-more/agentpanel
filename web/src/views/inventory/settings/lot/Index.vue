<template>
  <div class="lot-management">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="批次号">
          <el-input v-model="searchForm.lot_name" placeholder="请输入批次号" clearable />
        </el-form-item>
        <el-form-item label="产品编码">
          <el-input v-model="searchForm.product_code" placeholder="请输入产品编码" clearable />
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
          <span>批次列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新增批次</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="lot_name" label="批次号" min-width="140" />
        <el-table-column prop="product_code" label="产品编码" min-width="120" />
        <el-table-column prop="product_name" label="产品名称" min-width="150" />
        <el-table-column prop="expiration_date" label="有效期" width="120" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right" align="center">
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑批次' : '新增批次'" width="600px" @close="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="批次号" prop="lot_name">
          <el-input v-model="form.lot_name" placeholder="请输入批次号" />
        </el-form-item>
        <el-form-item label="产品编码" prop="product_code">
          <el-input v-model="form.product_code" placeholder="请输入产品编码" />
        </el-form-item>
        <el-form-item label="有效期">
          <el-date-picker v-model="form.expiration_date" type="date" placeholder="选择有效期" style="width: 100%" />
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
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, Edit, Delete } from '@element-plus/icons-vue'
import { getLotList, createLot, updateLot, deleteLot } from '@/api/inventory'

const loading = ref(false)
const submitLoading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const tableData = ref([])

const searchForm = reactive({ lot_name: '', product_code: '' })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })
const form = reactive({ lot_name: '', product_code: '', expiration_date: null })
const rules = {
  lot_name: [{ required: true, message: '请输入批次号', trigger: 'blur' }],
  product_code: [{ required: true, message: '请输入产品编码', trigger: 'blur' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getLotList({ page: pagination.page, page_size: pagination.pageSize, ...searchForm })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) { console.error('获取批次列表失败:', e) }
  finally { loading.value = false }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.lot_name = ''; searchForm.product_code = ''; handleSearch() }
const handleAdd = () => { isEdit.value = false; form.lot_name = ''; form.product_code = ''; form.expiration_date = null; dialogVisible.value = true }
const handleEdit = (row) => { isEdit.value = true; form.id = row.id; form.lot_name = row.lot_name; form.product_code = row.product_code; form.expiration_date = row.expiration_date; dialogVisible.value = true }
const handleSubmit = async () => {
  await formRef.value.validate()
  submitLoading.value = true
  try {
    if (isEdit.value) { await updateLot(form.id, form); ElMessage.success('更新成功') }
    else { await createLot(form); ElMessage.success('创建成功') }
    dialogVisible.value = false; fetchData()
  } catch (e) { console.error('提交失败:', e) }
  finally { submitLoading.value = false }
}
const handleDelete = async (row) => {
  try { await ElMessageBox.confirm(`确定要删除批次 "${row.lot_name}" 吗？`, '提示', { type: 'warning' })
    await deleteLot(row.id); ElMessage.success('删除成功'); fetchData()
  } catch (e) {}
}
const resetForm = () => { formRef.value?.resetFields() }

onMounted(() => { fetchData() })
</script>

<style lang="scss" scoped>
.lot-management {
  .search-card { margin-bottom: 16px;
    .search-form { display: flex; flex-wrap: wrap;
      .el-form-item { margin-bottom: 0; margin-right: 16px; }
    }
  }
  .table-card {
    .card-header { display: flex; justify-content: space-between; align-items: center; }
  }
  .pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
}
</style>


