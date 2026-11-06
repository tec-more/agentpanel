<template>
  <div class="quality-inspection">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="检验单号">
          <el-input v-model="searchForm.inspection_code" placeholder="请输入单号" clearable />
        </el-form-item>
        <el-form-item label="检验类型">
          <el-select v-model="searchForm.inspection_type" placeholder="请选择" clearable style="width: 120px">
            <el-option label="来料检验" value="incoming" />
            <el-option label="过程检验" value="process" />
            <el-option label="成品检验" value="finished" />
          </el-select>
        </el-form-item>
        <el-form-item label="结果">
          <el-select v-model="searchForm.result" placeholder="请选择" clearable style="width: 100px">
            <el-option label="合格" value="passed" />
            <el-option label="不合格" value="failed" />
            <el-option label="待检" value="pending" />
          </el-select>
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
          <span>质量检验列表</span>
          <el-button type="primary" :icon="Plus" @click="openAddDialog">新建检验单</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="inspection_code" label="检验单号" min-width="140" />
        <el-table-column prop="inspection_type" label="检验类型" width="100" align="center" />
        <el-table-column prop="product_name" label="产品名称" min-width="150" />
        <el-table-column prop="quantity" label="检验数量" width="100" align="center" />
        <el-table-column prop="passed_quantity" label="合格数量" width="100" align="center" />
        <el-table-column label="结果" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="resultTypeMap[row.result] || 'info'">
              {{ resultMap[row.result] || row.result }}
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
        <el-form-item label="检验单号" prop="inspection_code">
          <el-input v-model="formData.inspection_code" placeholder="请输入检验单号" />
        </el-form-item>
        <el-form-item label="检验类型" prop="inspection_type">
          <el-select v-model="formData.inspection_type" placeholder="请选择检验类型" style="width: 100%">
            <el-option label="来料检验" value="incoming" />
            <el-option label="过程检验" value="process" />
            <el-option label="成品检验" value="finished" />
          </el-select>
        </el-form-item>
        <el-form-item label="产品名称" prop="product_name">
          <el-input v-model="formData.product_name" placeholder="请输入产品名称" />
        </el-form-item>
        <el-form-item label="检验数量" prop="quantity">
          <el-input-number v-model="formData.quantity" :min="1" placeholder="请输入检验数量" style="width: 100%" />
        </el-form-item>
        <el-form-item label="合格数量" prop="passed_quantity">
          <el-input-number v-model="formData.passed_quantity" :min="0" placeholder="请输入合格数量" style="width: 100%" />
        </el-form-item>
        <el-form-item label="检验结果" prop="result">
          <el-select v-model="formData.result" placeholder="请选择检验结果" style="width: 100%">
            <el-option label="待检" value="pending" />
            <el-option label="合格" value="passed" />
            <el-option label="不合格" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注" prop="remarks">
          <el-input v-model="formData.remarks" type="textarea" :rows="3" placeholder="请输入备注" />
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
import { getInspectionList, createInspection } from '@/api/quality'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const tableData = ref([])

const searchForm = reactive({
  inspection_code: '',
  inspection_type: null,
  result: null
})

const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const dialogVisible = ref(false)
const dialogTitle = ref('新建检验单')
const submitLoading = ref(false)
const formRef = ref(null)

const formData = reactive({
  inspection_code: '',
  inspection_type: null,
  product_name: '',
  quantity: null,
  passed_quantity: null,
  result: null,
  remarks: ''
})

const formRules = {
  inspection_code: [{ required: true, message: '请输入检验单号', trigger: 'blur' }],
  inspection_type: [{ required: true, message: '请选择检验类型', trigger: 'change' }],
  product_name: [{ required: true, message: '请输入产品名称', trigger: 'blur' }],
  quantity: [{ required: true, message: '请输入检验数量', trigger: 'blur' }],
  result: [{ required: true, message: '请选择检验结果', trigger: 'change' }]
}

const resultMap = { pending: '待检', passed: '合格', failed: '不合格' }
const resultTypeMap = { pending: 'warning', passed: 'success', failed: 'danger' }

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getInspectionList({ page: pagination.page, page_size: pagination.pageSize, ...searchForm })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) { console.error('获取检验列表失败:', e) }
  finally { loading.value = false }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.inspection_code = ''; searchForm.inspection_type = null; searchForm.result = null; handleSearch() }

const openAddDialog = () => { dialogTitle.value = '新建检验单'; dialogVisible.value = true }

const handleSave = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      submitLoading.value = true
      try {
        await createInspection(formData)
        ElMessage.success('创建检验单成功')
        dialogVisible.value = false
        fetchData()
      } catch (e) { console.error('创建检验单失败:', e); ElMessage.error('创建检验单失败') }
      finally { submitLoading.value = false }
    }
  })
}

const handleDialogClose = () => {
  formRef.value?.resetFields()
  Object.keys(formData).forEach(k => { formData[k] = k === 'passed_quantity' ? null : (k === 'status' ? 'pending' : '') })
}

onMounted(() => { fetchData() })
</script>

<style lang="scss" scoped>
.quality-inspection {
  .search-card { margin-bottom: 16px;
    .search-form { display: flex; flex-wrap: wrap;
      .el-form-item { margin-bottom: 0; margin-right: 16px; }
    }
  }
  .table-card { .card-header { display: flex; justify-content: space-between; align-items: center; } }
  .pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
}
</style>

