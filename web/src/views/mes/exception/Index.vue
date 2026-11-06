<template>
  <div class="exception-manage">
    <el-card>
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>生产异常管理</span>
          <el-button type="primary" @click="showReportDialog = true">上报异常</el-button>
        </div>
      </template>
      <el-form :inline="true" :model="queryForm" class="query-form">
        <el-form-item label="异常类型">
          <el-select v-model="queryForm.exception_type" placeholder="全部" clearable style="width: 140px;">
            <el-option label="设备故障" value="equipment_failure" />
            <el-option label="质量异常" value="quality_issue" />
            <el-option label="物料异常" value="material_issue" />
            <el-option label="工艺异常" value="process_issue" />
            <el-option label="安全异常" value="safety_issue" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="严重程度">
          <el-select v-model="queryForm.severity" placeholder="全部" clearable style="width: 120px;">
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryForm.status" placeholder="全部" clearable style="width: 120px;">
            <el-option label="待处理" value="pending" />
            <el-option label="处理中" value="processing" />
            <el-option label="已解决" value="resolved" />
            <el-option label="已关闭" value="closed" />
          </el-select>
        </el-form-item>
        <el-form-item label="工作中心">
          <el-input v-model="queryForm.work_center_code" placeholder="请输入" clearable />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchList">查询</el-button>
          <el-button @click="resetQuery">重置</el-button>
        </el-form-item>
      </el-form>
      <el-table :data="tableData" border stripe v-loading="loading">
        <el-table-column prop="exception_code" label="异常编号" width="160" />
        <el-table-column prop="exception_type" label="异常类型" width="120">
          <template #default="{ row }">
            <el-tag>{{ typeMap[row.exception_type] || row.exception_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="severity" label="严重程度" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="severityTag[row.severity] || 'info'">{{ severityMap[row.severity] || row.severity }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="wo_code" label="工单编码" width="150" />
        <el-table-column prop="work_center_code" label="工作中心" width="120" />
        <el-table-column prop="description" label="异常描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="reporter" label="上报人" width="100" />
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTag[row.status] || 'info'">{{ statusMap[row.status] || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="上报时间" width="180" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'pending'" type="primary" size="small" @click="openHandleDialog(row)">处理</el-button>
          </template>
        </el-table-column>
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

    <el-dialog v-model="showReportDialog" title="上报异常" width="600px">
      <el-form :model="reportForm" label-width="100px">
        <el-form-item label="工单编码" required>
          <el-input v-model="reportForm.wo_code" />
        </el-form-item>
        <el-form-item label="工作中心" required>
          <el-input v-model="reportForm.work_center_code" />
        </el-form-item>
        <el-form-item label="异常类型" required>
          <el-select v-model="reportForm.exception_type" style="width: 100%;">
            <el-option label="设备故障" value="equipment_failure" />
            <el-option label="质量异常" value="quality_issue" />
            <el-option label="物料异常" value="material_issue" />
            <el-option label="工艺异常" value="process_issue" />
            <el-option label="安全异常" value="safety_issue" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="严重程度" required>
          <el-select v-model="reportForm.severity" style="width: 100%;">
            <el-option label="低" value="low" />
            <el-option label="中" value="medium" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="critical" />
          </el-select>
        </el-form-item>
        <el-form-item label="异常描述" required>
          <el-input v-model="reportForm.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="上报人" required>
          <el-input v-model="reportForm.reporter" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReportDialog = false">取消</el-button>
        <el-button type="primary" @click="submitReport" :loading="submitting">提交</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showHandleDialog" title="处理异常" width="600px">
      <el-form :model="handleForm" label-width="100px">
        <el-form-item label="处理措施" required>
          <el-input v-model="handleForm.handle_measure" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="处理人" required>
          <el-input v-model="handleForm.handler" />
        </el-form-item>
        <el-form-item label="是否恢复工单">
          <el-switch v-model="handleForm.resume_work_order" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showHandleDialog = false">取消</el-button>
        <el-button type="primary" @click="submitHandle" :loading="handling">确认处理</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getExceptionList, reportException, handleException } from '@/api/mes'

const loading = ref(false)
const submitting = ref(false)
const handling = ref(false)
const tableData = ref([])
const total = ref(0)
const showReportDialog = ref(false)
const showHandleDialog = ref(false)
const currentExceptionId = ref(null)

const typeMap = { equipment_failure: '设备故障', quality_issue: '质量异常', material_issue: '物料异常', process_issue: '工艺异常', safety_issue: '安全异常', other: '其他' }
const severityMap = { low: '低', medium: '中', high: '高', critical: '紧急' }
const severityTag = { low: 'info', medium: 'warning', high: 'danger', critical: 'danger' }
const statusMap = { pending: '待处理', processing: '处理中', resolved: '已解决', closed: '已关闭' }
const statusTag = { pending: 'danger', processing: 'warning', resolved: 'success', closed: 'info' }

const queryForm = ref({ page: 1, page_size: 20, exception_type: '', severity: '', status: '', work_center_code: '' })

const reportForm = ref({ wo_code: '', work_center_code: '', exception_type: '', severity: '', description: '', reporter: '' })
const handleForm = ref({ handle_measure: '', handler: '', resume_work_order: false })

const fetchList = async () => {
  loading.value = true
  try {
    const params = { ...queryForm.value }
    Object.keys(params).forEach(k => { if (!params[k]) delete params[k] })
    const res = await getExceptionList(params)
    const d = res.data?.data || res.data || {}
    tableData.value = d.items || []
    total.value = d.total || 0
  } catch (e) { ElMessage.error('获取异常列表失败') }
  loading.value = false
}

const resetQuery = () => {
  queryForm.value = { page: 1, page_size: 20, exception_type: '', severity: '', status: '', work_center_code: '' }
  fetchList()
}

const submitReport = async () => {
  submitting.value = true
  try {
    await reportException(reportForm.value)
    ElMessage.success('异常上报成功')
    showReportDialog.value = false
    reportForm.value = { wo_code: '', work_center_code: '', exception_type: '', severity: '', description: '', reporter: '' }
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '上报失败') }
  submitting.value = false
}

const openHandleDialog = (row) => {
  currentExceptionId.value = row.id
  handleForm.value = { handle_measure: '', handler: '', resume_work_order: false }
  showHandleDialog.value = true
}

const submitHandle = async () => {
  handling.value = true
  try {
    await handleException(currentExceptionId.value, handleForm.value)
    ElMessage.success('异常处理成功')
    showHandleDialog.value = false
    fetchList()
  } catch (e) { ElMessage.error(e.response?.data?.detail || '处理失败') }
  handling.value = false
}

onMounted(fetchList)
</script>