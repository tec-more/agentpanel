<template>
  <div class="quality-standard">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="标准编号">
          <el-input v-model="searchForm.standard_code" placeholder="请输入编号" clearable />
        </el-form-item>
        <el-form-item label="标准名称">
          <el-input v-model="searchForm.standard_name" placeholder="请输入名称" clearable />
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
          <span>检验标准列表</span>
          <el-button type="primary" :icon="Plus" @click="openAddDialog">新建标准</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="standard_code" label="标准编号" min-width="120" />
        <el-table-column prop="standard_name" label="标准名称" min-width="150" />
        <el-table-column prop="product_code" label="产品编码" min-width="120" />
        <el-table-column prop="product_name" label="产品名称" min-width="150" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
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

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="600px"
      @close="handleDialogClose"
    >
      <el-form
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-width="100px"
      >
        <el-form-item label="标准编号" prop="standard_code">
          <el-input v-model="formData.standard_code" placeholder="请输入标准编号" />
        </el-form-item>
        <el-form-item label="标准名称" prop="standard_name">
          <el-input v-model="formData.standard_name" placeholder="请输入标准名称" />
        </el-form-item>
        <el-form-item label="产品编码" prop="product_code">
          <el-input v-model="formData.product_code" placeholder="请输入产品编码" />
        </el-form-item>
        <el-form-item label="产品名称" prop="product_name">
          <el-input v-model="formData.product_name" placeholder="请输入产品名称" />
        </el-form-item>
        <el-form-item label="检验项目" prop="items">
          <el-input v-model="formData.items" type="textarea" :rows="3" placeholder="请输入检验项目，多个用逗号分隔" />
        </el-form-item>
        <el-form-item label="检验方法" prop="method">
          <el-input v-model="formData.method" type="textarea" :rows="3" placeholder="请输入检验方法" />
        </el-form-item>
        <el-form-item label="判定标准" prop="criteria">
          <el-input v-model="formData.criteria" type="textarea" :rows="3" placeholder="请输入判定标准" />
        </el-form-item>
        <el-form-item label="是否启用" prop="is_active">
          <el-switch v-model="formData.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSave">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'
import { getStandardList, createStandard } from '@/api/quality'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const tableData = ref([])

const searchForm = reactive({ standard_code: '', standard_name: '' })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const dialogVisible = ref(false)
const dialogTitle = ref('新建检验标准')
const submitLoading = ref(false)
const formRef = ref(null)

const formData = reactive({
  standard_code: '',
  standard_name: '',
  product_code: '',
  product_name: '',
  items: '',
  method: '',
  criteria: '',
  is_active: true
})

const formRules = {
  standard_code: [{ required: true, message: '请输入标准编号', trigger: 'blur' }],
  standard_name: [{ required: true, message: '请输入标准名称', trigger: 'blur' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getStandardList({ page: pagination.page, page_size: pagination.pageSize, ...searchForm })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) { console.error('获取标准列表失败:', e) }
  finally { loading.value = false }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.standard_code = ''; searchForm.standard_name = ''; handleSearch() }

const openAddDialog = () => { dialogTitle.value = '新建检验标准'; dialogVisible.value = true }

const handleSave = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      submitLoading.value = true
      try {
        await createStandard(formData)
        ElMessage.success('创建检验标准成功')
        dialogVisible.value = false
        fetchData()
      } catch (e) { console.error('创建检验标准失败:', e); ElMessage.error('创建检验标准失败') }
      finally { submitLoading.value = false }
    }
  })
}

const handleDialogClose = () => {
  formRef.value?.resetFields()
  Object.keys(formData).forEach(k => { formData[k] = k === 'is_active' ? true : '' })
}

onMounted(() => { fetchData() })
</script>

<style lang="scss" scoped>
.quality-standard {
  .search-card { margin-bottom: 16px;
    .search-form { display: flex; flex-wrap: wrap;
      .el-form-item { margin-bottom: 0; margin-right: 16px; }
    }
  }
  .table-card { .card-header { display: flex; justify-content: space-between; align-items: center; } }
  .pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
}
</style>

