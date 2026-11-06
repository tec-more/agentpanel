<template>
  <div class="production-report">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>生产报工</span>
          <el-button type="primary" @click="showReportDialog = true">提交报工</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="queryForm" class="query-form">
        <el-form-item label="工单编码">
          <el-input v-model="queryForm.wo_code" placeholder="请输入" clearable />
        </el-form-item>
        <el-form-item label="制造单编码">
          <el-input v-model="queryForm.mo_code" placeholder="请输入" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchList">查询</el-button>
          <el-button @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>
      <el-table :data="tableData" border stripe v-loading="loading">
        <el-table-column prop="report_code" label="报工单号" width="180" />
        <el-table-column prop="wo_code" label="工单编码" width="160" />
        <el-table-column prop="mo_code" label="制造单编码" width="160" />
        <el-table-column prop="process_code" label="工序" width="120" />
        <el-table-column prop="operator" label="操作员" width="100" />
        <el-table-column prop="qualified_quantity" label="合格数量" width="100" />
        <el-table-column prop="scrap_quantity" label="报废数量" width="100" />
        <el-table-column prop="actual_work_hours" label="工时(分钟)" width="110" />
        <el-table-column prop="batch_no" label="批次号" width="160" />
        <el-table-column prop="created_at" label="报工时间" width="180" />
      </el-table>
      <el-pagination
        v-model:current-page="queryForm.page"
        v-model:page-size="queryForm.page_size"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="fetchList"
        style="margin-top: 16px; justify-content: flex-end;"
      />
    </el-card>

    <el-dialog v-model="showReportDialog" title="提交报工" width="600px">
      <el-form :model="reportForm" label-width="100px">
        <el-form-item label="工单编码" required>
          <el-input v-model="reportForm.wo_code" />
        </el-form-item>
        <el-form-item label="制造单编码" required>
          <el-input v-model="reportForm.mo_code" />
        </el-form-item>
        <el-form-item label="工序编码" required>
          <el-input v-model="reportForm.process_code" />
        </el-form-item>
        <el-form-item label="工作中心" required>
          <el-input v-model="reportForm.work_center_code" />
        </el-form-item>
        <el-form-item label="设备编码" required>
          <el-input v-model="reportForm.equipment_code" />
        </el-form-item>
        <el-form-item label="班次编码" required>
          <el-input v-model="reportForm.shift_code" />
        </el-form-item>
        <el-form-item label="批次号" required>
          <el-input v-model="reportForm.batch_no" />
        </el-form-item>
        <el-form-item label="合格数量" required>
          <el-input-number v-model="reportForm.qualified_quantity" :min="0" />
        </el-form-item>
        <el-form-item label="报废数量">
          <el-input-number v-model="reportForm.scrap_quantity" :min="0" />
        </el-form-item>
        <el-form-item label="开始时间" required>
          <el-date-picker v-model="reportForm.actual_start_time" type="datetime" />
        </el-form-item>
        <el-form-item label="结束时间" required>
          <el-date-picker v-model="reportForm.actual_end_time" type="datetime" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="reportForm.remark" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReportDialog = false">取消</el-button>
        <el-button type="primary" @click="submitReport" :loading="submitting">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getProductionReportList, submitProductionReport } from '@/api/mes'

const loading = ref(false)
const submitting = ref(false)
const tableData = ref([])
const total = ref(0)
const showReportDialog = ref(false)

const queryForm = ref({ page: 1, page_size: 20, wo_code: '', mo_code: '' })

const reportForm = ref({
  wo_code: '', mo_code: '', process_code: '', work_center_code: '',
  equipment_code: '', shift_code: '', batch_no: '',
  qualified_quantity: 0, scrap_quantity: 0,
  actual_start_time: '', actual_end_time: '', remark: ''
})

const fetchList = async () => {
  loading.value = true
  try {
    const res = await getProductionReportList(queryForm.value)
    const d = res.data?.data || res.data || {}
    tableData.value = d.items || []
    total.value = d.total || 0
  } catch (e) {
    ElMessage.error('获取报工记录失败')
  }
  loading.value = false
}

const resetQuery = () => {
  queryForm.value = { page: 1, page_size: 20, wo_code: '', mo_code: '' }
  fetchList()
}

const submitReport = async () => {
  submitting.value = true
  try {
    await submitProductionReport(reportForm.value)
    ElMessage.success('报工成功')
    showReportDialog.value = false
    reportForm.value = {
      wo_code: '', mo_code: '', process_code: '', work_center_code: '',
      equipment_code: '', shift_code: '', batch_no: '',
      qualified_quantity: 0, scrap_quantity: 0,
      actual_start_time: '', actual_end_time: '', remark: ''
    }
    fetchList()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '报工失败')
  }
  submitting.value = false
}

onMounted(fetchList)
</script>