<template>
  <div class="audit-reports">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="报告类型">
          <el-select v-model="searchForm.report_type" placeholder="请选择" clearable style="width: 150px;">
            <el-option label="日报" value="daily" />
            <el-option label="周报" value="weekly" />
            <el-option label="月报" value="monthly" />
            <el-option label="年报" value="yearly" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="报告状态">
          <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 150px;">
            <el-option label="草稿" value="draft" />
            <el-option label="已生成" value="generated" />
            <el-option label="已发布" value="published" />
            <el-option label="已归档" value="archived" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 360px"
          />
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
          <span>审计报告列表</span>
          <el-button type="primary" :icon="Plus" @click="handleCreate">生成报告</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="report_name" label="报告标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="report_type" label="报告类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="getReportTypeTagType(row.report_type)">
              {{ getReportTypeLabel(row.report_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="start_time" label="开始日期" width="120" />
        <el-table-column prop="end_time" label="结束日期" width="120" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="getStatusTagType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="generated_by_name" label="创建人" width="120" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link :icon="View" @click="handleDetail(row)">查看</el-button>
              <el-button type="primary" link :icon="Download" @click="handleDownload(row)">下载</el-button>
              <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">编辑</el-button>
            </div>
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

    <el-dialog v-model="detailDialogVisible" title="报告详情" width="900px">
      <el-descriptions v-if="currentReport" :column="2" border>
        <el-descriptions-item label="ID">{{ currentReport.id }}</el-descriptions-item>
        <el-descriptions-item label="报告类型">
          <el-tag size="small" :type="getReportTypeTagType(currentReport.report_type)">
            {{ getReportTypeLabel(currentReport.report_type) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="报告标题" :span="2">{{ currentReport.report_name }}</el-descriptions-item>
        <el-descriptions-item label="开始日期">{{ currentReport.start_time }}</el-descriptions-item>
        <el-descriptions-item label="结束日期">{{ currentReport.end_time }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag size="small" :type="getStatusTagType(currentReport.status)">
            {{ getStatusLabel(currentReport.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建人">{{ currentReport.generated_by_name }}</el-descriptions-item>
        <el-descriptions-item label="报告摘要" :span="2">{{ currentReport.summary }}</el-descriptions-item>
        <el-descriptions-item label="报告内容" :span="2">
          <pre v-if="currentReport.report_data" style="white-space: pre-wrap; max-height: 400px; overflow-y: auto;">{{ currentReport.report_data }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ currentReport.created_at }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ currentReport.updated_at }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button type="primary" :icon="Download" @click="handleDownload(currentReport)">下载</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="createDialogVisible" :title="isEdit ? '编辑报告' : '生成报告'" width="700px" @close="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="报告标题" prop="report_name">
          <el-input v-model="form.report_name" placeholder="请输入报告标题" />
        </el-form-item>
        <el-form-item label="报告类型" prop="report_type">
          <el-select v-model="form.report_type" placeholder="请选择报告类型" style="width: 100%;">
            <el-option label="日报" value="daily" />
            <el-option label="周报" value="weekly" />
            <el-option label="月报" value="monthly" />
            <el-option label="年报" value="yearly" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围" prop="date_range">
          <el-date-picker
            v-model="form.date_range"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="报告摘要" prop="summary">
          <el-input v-model="form.summary" type="textarea" :rows="3" placeholder="请输入报告摘要" />
        </el-form-item>
        <el-form-item label="包含模块" prop="modules">
          <el-checkbox-group v-model="form.modules">
            <el-checkbox label="审计日志">审计日志</el-checkbox>
            <el-checkbox label="数据变更">数据变更</el-checkbox>
            <el-checkbox label="登录审计">登录审计</el-checkbox>
            <el-checkbox label="风险审计">风险审计</el-checkbox>
            <el-checkbox label="全链路追踪">全链路追踪</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, Plus, View, Edit, Download } from '@element-plus/icons-vue'
import { getReportList, getReportDetail, createReport as apiCreateReport, updateReport as apiUpdateReport, downloadReport } from '@/api/audit'

const loading = ref(false)
const submitLoading = ref(false)
const detailDialogVisible = ref(false)
const createDialogVisible = ref(false)
const isEdit = ref(false)
const currentReport = ref(null)
const formRef = ref(null)

const tableData = ref([])
const dateRange = ref([])

const searchForm = reactive({
  report_type: '',
  status: '',
  start_time: null,
  end_time: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const form = ref({
  report_name: '',
  report_type: 'daily',
  start_time: '',
  end_time: '',
  summary: '',
  modules: [],
  date_range: []
})

const rules = {
  report_name: [{ required: true, message: '请输入报告标题', trigger: 'blur' }],
  report_type: [{ required: true, message: '请选择报告类型', trigger: 'change' }],
  date_range: [{ required: true, message: '请选择时间范围', trigger: 'change' }]
}

const getReportTypeLabel = (type) => {
  const labels = {
    daily: '日报',
    weekly: '周报',
    monthly: '月报',
    yearly: '年报',
    custom: '自定义'
  }
  return labels[type] || type
}

const getReportTypeTagType = (type) => {
  const types = {
    daily: 'primary',
    weekly: 'success',
    monthly: 'warning',
    yearly: 'danger',
    custom: 'info'
  }
  return types[type] || 'info'
}

const getStatusLabel = (status) => {
  const labels = {
    draft: '草稿',
    generated: '已生成',
    published: '已发布',
    archived: '已归档'
  }
  return labels[status] || status
}

const getStatusTagType = (status) => {
  const types = {
    draft: 'info',
    generated: 'warning',
    published: 'success',
    archived: 'info'
  }
  return types[status] || 'info'
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_time = dateRange.value[0]
      params.end_time = dateRange.value[1]
    }
    const res = await getReportList(params)
    tableData.value = res.data.items || res.data || []
    pagination.total = res.data.total || tableData.value.length
  } catch (e) {
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.report_type = ''
  searchForm.status = ''
  dateRange.value = []
  handleSearch()
}

const handleDetail = async (row) => {
  const res = await getReportDetail(row.id)
  currentReport.value = res.data
  detailDialogVisible.value = true
}

const handleDownload = async (row) => {
  try {
    const response = await downloadReport(row.id)
    const blob = new Blob([response.data], { type: 'application/pdf' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `${row.report_name}.pdf`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('下载成功')
  } catch (e) {
    ElMessage.error('下载失败')
  }
}

const handleCreate = () => {
  isEdit.value = false
  form.value = {
    report_name: '',
    report_type: 'daily',
    start_time: '',
    end_time: '',
    summary: '',
    modules: [],
    date_range: []
  }
  createDialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  currentReport.value = row
  form.value = {
    report_name: row.report_name,
    report_type: row.report_type,
    start_time: row.start_time,
    end_time: row.end_time,
    summary: row.summary || '',
    modules: row.modules || [],
    date_range: [row.start_time, row.end_time]
  }
  createDialogVisible.value = true
}

const handleSubmit = async () => {
  await formRef.value.validate()
  if (form.value.date_range && form.value.date_range.length === 2) {
    form.value.start_time = form.value.date_range[0]
    form.value.end_time = form.value.date_range[1]
  }
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await apiUpdateReport(currentReport.value.id, {
        report_name: form.value.report_name,
        summary: form.value.summary
      })
      ElMessage.success('更新成功')
    } else {
      await apiCreateReport({
        report_name: form.value.report_name,
        report_type: form.value.report_type,
        start_time: form.value.start_time,
        end_time: form.value.end_time,
        summary: form.value.summary,
        modules: form.value.modules
      })
      ElMessage.success('生成成功')
    }
    createDialogVisible.value = false
    fetchData()
  } catch (e) {
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
.audit-reports {
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



