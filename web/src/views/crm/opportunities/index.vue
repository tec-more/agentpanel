<template>
  <div class="opportunity-list">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 120px">
            <el-option label="进行中" value="in_progress" />
            <el-option label="赢单" value="won" />
            <el-option label="输单" value="lost" />
          </el-select>
        </el-form-item>
        <el-form-item label="阶段">
          <el-select v-model="searchForm.stage" placeholder="请选择" clearable style="width: 140px">
            <el-option v-for="s in stageOptions" :key="s.code" :label="s.name" :value="s.code" />
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
          <span>商机列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新建商机</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="name" label="商机名称" min-width="160" />
        <el-table-column prop="customer_id" label="客户ID" width="90" align="center" />
        <el-table-column label="阶段" width="120" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ stageName(row.stage) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="expected_amount" label="预期金额" width="120" align="right">
          <template #default="{ row }">¥{{ formatAmount(row.expected_amount) }}</template>
        </el-table-column>
        <el-table-column prop="probability" label="成交概率" width="100" align="center">
          <template #default="{ row }">
            <el-progress :percentage="row.probability || 0" :stroke-width="10" />
          </template>
        </el-table-column>
        <el-table-column prop="expected_close_date" label="预计成交" width="120" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'won' ? 'success' : row.status === 'lost' ? 'danger' : 'warning'" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="280" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">编辑</el-button>
            <el-button v-if="row.status === 'in_progress'" type="success" link @click="handleWin(row)">赢单</el-button>
            <el-button v-if="row.status === 'in_progress'" type="warning" link @click="handleLose(row)">输单</el-button>
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑商机' : '新建商机'" width="560px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="商机名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入商机名称" />
        </el-form-item>
        <el-form-item label="客户ID" prop="customer_id">
          <el-input-number v-model="form.customer_id" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="阶段" prop="stage">
          <el-select v-model="form.stage" placeholder="请选择阶段" style="width: 100%">
            <el-option v-for="s in stageOptions" :key="s.code" :label="s.name" :value="s.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="预期金额" prop="expected_amount">
          <el-input-number v-model="form.expected_amount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="成交概率">
          <el-input-number v-model="form.probability" :min="0" :max="100" style="width: 100%" />
        </el-form-item>
        <el-form-item label="预计成交">
          <el-date-picker v-model="form.expected_close_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="winDialogVisible" title="赢单" width="420px">
      <el-form :model="winForm" label-width="100px">
        <el-form-item label="成交金额">
          <el-input-number v-model="winForm.actual_amount" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="winDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitWin">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="loseDialogVisible" title="输单" width="420px">
      <el-form :model="loseForm" :rules="loseRules" label-width="100px">
        <el-form-item label="输单原因" prop="lost_reason">
          <el-input v-model="loseForm.lost_reason" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="loseDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitLose">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, Edit, Delete } from '@element-plus/icons-vue'
import { getOpportunityList, createOpportunity, updateOpportunity, deleteOpportunity, winOpportunity, loseOpportunity, getStages } from '@/api/crm'

const loading = ref(false)
const submitting = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const winDialogVisible = ref(false)
const loseDialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const stageOptions = ref([])

const searchForm = reactive({ status: null, stage: null })

const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const form = reactive({
  id: null, name: '', customer_id: null, stage: '', expected_amount: null,
  probability: null, expected_close_date: null
})

const winForm = reactive({ actual_amount: null })
const loseForm = reactive({ lost_reason: '' })

const rules = {
  name: [{ required: true, message: '请输入商机名称', trigger: 'blur' }],
  customer_id: [{ required: true, message: '请输入客户ID', trigger: 'blur' }],
  stage: [{ required: true, message: '请选择阶段', trigger: 'change' }],
  expected_amount: [{ required: true, message: '请输入预期金额', trigger: 'blur' }]
}

const loseRules = {
  lost_reason: [{ required: true, message: '请输入输单原因', trigger: 'blur' }]
}

const statusLabel = (s) => ({ in_progress: '进行中', won: '赢单', lost: '输单' }[s] || s)
const stageName = (code) => { const s = stageOptions.value.find(x => x.code === code); return s ? s.name : code }
const formatAmount = (v) => v ? Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '0.00'

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getOpportunityList({ page: pagination.page, page_size: pagination.pageSize, ...searchForm })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) { console.error('获取商机列表失败:', e) }
  finally { loading.value = false }
}

const fetchStages = async () => {
  try {
    const res = await getStages()
    stageOptions.value = res.data || []
  } catch (e) { console.error('获取阶段失败:', e) }
}

const resetForm = () => {
  form.id = null; form.name = ''; form.customer_id = null; form.stage = ''
  form.expected_amount = null; form.probability = null; form.expected_close_date = null
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.status = null; searchForm.stage = null; handleSearch() }
const handleAdd = () => { isEdit.value = false; resetForm(); dialogVisible.value = true }
const handleEdit = (row) => { isEdit.value = true; Object.assign(form, row); dialogVisible.value = true }

const handleSubmit = async () => {
  try {
    await formRef.value.validate()
    submitting.value = true
    const data = {
      name: form.name, customer_id: form.customer_id, stage: form.stage,
      expected_amount: form.expected_amount, probability: form.probability || null,
      expected_close_date: form.expected_close_date || null
    }
    if (isEdit.value) { await updateOpportunity(form.id, data); ElMessage.success('更新成功') }
    else { await createOpportunity(data); ElMessage.success('创建成功') }
    dialogVisible.value = false; fetchData()
  } catch (e) { if (e !== false) ElMessage.error(e.message || '操作失败') }
  finally { submitting.value = false }
}

const handleWin = (row) => { winForm.actual_amount = row.expected_amount; winDialogVisible.value = true }
const submitWin = async () => {
  try {
    submitting.value = true
    await winOpportunity(form.id, { actual_amount: winForm.actual_amount, create_order: false })
    ElMessage.success('赢单成功'); winDialogVisible.value = false; fetchData()
  } catch (e) { ElMessage.error(e.message || '操作失败') }
  finally { submitting.value = false }
}

const handleLose = (row) => { loseForm.lost_reason = ''; loseDialogVisible.value = true }
const submitLose = async () => {
  try {
    if (!loseForm.lost_reason.trim()) { ElMessage.warning('请输入输单原因'); return }
    submitting.value = true
    await loseOpportunity(form.id, { lost_reason: loseForm.lost_reason })
    ElMessage.success('输单成功'); loseDialogVisible.value = false; fetchData()
  } catch (e) { ElMessage.error(e.message || '操作失败') }
  finally { submitting.value = false }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除商机 "${row.name}" 吗？`, '提示', { type: 'warning' })
    await deleteOpportunity(row.id); ElMessage.success('删除成功'); fetchData()
  } catch (e) {}
}

onMounted(() => { fetchStages(); fetchData() })
</script>

<style lang="scss" scoped>
.opportunity-list {
  .search-card { margin-bottom: 16px; }
  .table-card { .card-header { display: flex; justify-content: space-between; align-items: center; } }
  .pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
}
</style>
