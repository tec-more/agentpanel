<template>
  <div class="production-dashboard">
    <el-row :gutter="16" class="stat-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-title">OEE综合效率</div>
          <div class="stat-value">{{ oee.overall || '0%' }}</div>
          <div class="stat-detail">
            <span>可用率: {{ oee.availability || '0%' }}</span>
            <span>性能率: {{ oee.performance || '0%' }}</span>
            <span>良品率: {{ oee.quality || '0%' }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-title">今日产量</div>
          <div class="stat-value">{{ production.today_output || 0 }}</div>
          <div class="stat-detail">
            <span>计划: {{ production.planned_output || 0 }}</span>
            <span>完成率: {{ production.completion_rate || '0%' }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-title">合格率</div>
          <div class="stat-value">{{ production.qualified_rate || '0%' }}</div>
          <div class="stat-detail">
            <span>合格: {{ production.qualified_quantity || 0 }}</span>
            <span>报废: {{ production.scrap_quantity || 0 }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-title">在制工单</div>
          <div class="stat-value">{{ progress.length || 0 }}</div>
          <div class="stat-detail">
            <span>生产中: {{ processingCount }}</span>
            <span>已暂停: {{ suspendedCount }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-bottom: 16px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>OEE统计</span>
          <div>
            <el-select v-model="oeePeriod" style="width: 120px; margin-right: 8px;" @change="fetchOee">
              <el-option label="按天" value="day" />
              <el-option label="按周" value="week" />
              <el-option label="按月" value="month" />
            </el-select>
            <el-input v-model="oeeWorkCenter" placeholder="工作中心" clearable style="width: 160px;" @clear="fetchOee" @keyup.enter="fetchOee" />
          </div>
        </div>
      </template>
      <el-table :data="oeeTableData" border stripe v-loading="oeeLoading">
        <el-table-column prop="work_center_code" label="工作中心" width="140" />
        <el-table-column prop="work_center_name" label="工作中心名称" width="160" />
        <el-table-column prop="availability" label="可用率" width="100" />
        <el-table-column prop="performance" label="性能率" width="100" />
        <el-table-column prop="quality" label="良品率" width="100" />
        <el-table-column prop="oee" label="OEE" width="100">
          <template #default="{ row }">
            <el-tag :type="parseFloat(row.oee) >= 85 ? 'success' : parseFloat(row.oee) >= 60 ? 'warning' : 'danger'">
              {{ row.oee }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="period" label="统计周期" />
      </el-table>
    </el-card>

    <el-card style="margin-bottom: 16px;">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span>产量统计</span>
          <div>
            <el-select v-model="prodPeriod" style="width: 120px; margin-right: 8px;" @change="fetchProduction">
              <el-option label="按天" value="day" />
              <el-option label="按周" value="week" />
              <el-option label="按月" value="month" />
            </el-select>
            <el-input v-model="prodWorkCenter" placeholder="工作中心" clearable style="width: 160px;" @clear="fetchProduction" @keyup.enter="fetchProduction" />
          </div>
        </div>
      </template>
      <el-table :data="prodTableData" border stripe v-loading="prodLoading">
        <el-table-column prop="work_center_code" label="工作中心" width="140" />
        <el-table-column prop="work_center_name" label="工作中心名称" width="160" />
        <el-table-column prop="planned_output" label="计划产量" width="100" />
        <el-table-column prop="actual_output" label="实际产量" width="100" />
        <el-table-column prop="qualified_quantity" label="合格数量" width="100" />
        <el-table-column prop="scrap_quantity" label="报废数量" width="100" />
        <el-table-column prop="completion_rate" label="完成率" width="100">
          <template #default="{ row }">
            <el-progress :percentage="parseFloat(row.completion_rate) || 0" :stroke-width="10" />
          </template>
        </el-table-column>
        <el-table-column prop="period" label="统计周期" />
      </el-table>
    </el-card>

    <el-card>
      <template #header>
        <span>实时生产进度</span>
      </template>
      <el-table :data="progress" border stripe v-loading="progressLoading">
        <el-table-column prop="wo_code" label="工单编码" width="160" />
        <el-table-column prop="mo_code" label="制造单编码" width="160" />
        <el-table-column prop="product_code" label="产品编码" width="120" />
        <el-table-column prop="product_name" label="产品名称" width="140" />
        <el-table-column prop="work_center_code" label="工作中心" width="120" />
        <el-table-column prop="quantity" label="计划数量" width="100" />
        <el-table-column prop="actual_quantity" label="完成数量" width="100" />
        <el-table-column label="进度" width="180">
          <template #default="{ row }">
            <el-progress :percentage="row.quantity ? Math.round((row.actual_quantity || 0) / row.quantity * 100) : 0" :stroke-width="12" />
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'processing' ? 'primary' : row.status === 'suspended' ? 'warning' : 'info'">
              {{ statusMap[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getDashboardOee, getDashboardProduction, getDashboardProgress } from '@/api/mes'

const oee = ref({})
const production = ref({})
const progress = ref([])
const oeeLoading = ref(false)
const prodLoading = ref(false)
const progressLoading = ref(false)
const oeePeriod = ref('day')
const oeeWorkCenter = ref('')
const prodPeriod = ref('day')
const prodWorkCenter = ref('')
const oeeTableData = ref([])
const prodTableData = ref([])

const statusMap = {
  pending: '待下发', released: '已下发', processing: '生产中',
  suspended: '已暂停', completed: '已完工', closed: '已关闭'
}

const processingCount = computed(() => progress.value.filter(r => r.status === 'processing').length)
const suspendedCount = computed(() => progress.value.filter(r => r.status === 'suspended').length)

const fetchOee = async () => {
  oeeLoading.value = true
  try {
    const params = { period: oeePeriod.value }
    if (oeeWorkCenter.value) params.work_center_code = oeeWorkCenter.value
    const res = await getDashboardOee(params)
    const d = res.data?.data || res.data || {}
    oee.value = d.summary || d
    oeeTableData.value = Array.isArray(d.items || d) ? (d.items || d) : [d]
  } catch (e) { ElMessage.error('获取OEE数据失败') }
  oeeLoading.value = false
}

const fetchProduction = async () => {
  prodLoading.value = true
  try {
    const params = { period: prodPeriod.value }
    if (prodWorkCenter.value) params.work_center_code = prodWorkCenter.value
    const res = await getDashboardProduction(params)
    const d = res.data?.data || res.data || {}
    production.value = d.summary || d
    prodTableData.value = Array.isArray(d.items || d) ? (d.items || d) : [d]
  } catch (e) { ElMessage.error('获取产量数据失败') }
  prodLoading.value = false
}

const fetchProgress = async () => {
  progressLoading.value = true
  try {
    const res = await getDashboardProgress()
    const d = res.data?.data || res.data || {}
    progress.value = d.items || d || []
  } catch (e) { ElMessage.error('获取生产进度失败') }
  progressLoading.value = false
}

onMounted(() => { fetchOee(); fetchProduction(); fetchProgress() })
</script>

<style lang="scss" scoped>
.production-dashboard {
  .stat-row { margin-bottom: 16px; }
  .stat-card {
    text-align: center;
    .stat-title { font-size: 14px; color: #909399; margin-bottom: 8px; }
    .stat-value { font-size: 28px; font-weight: bold; color: #303133; margin-bottom: 8px; }
    .stat-detail {
      font-size: 12px; color: #909399;
      span { margin: 0 8px; }
    }
  }
}
</style>