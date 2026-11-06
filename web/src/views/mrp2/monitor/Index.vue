<template>
  <div class="monitor-index">
    <el-card shadow="never" class="search-card">
      <template #header>
        <div class="card-header">
          <span>计划执行监控</span>
        </div>
      </template>
      
      <div class="search-row">
        <el-form :inline="true" :model="searchForm" class="search-form">
          <el-form-item label="监控编码">
            <el-input v-model="searchForm.monitor_code" placeholder="搜索监控编码" clearable />
          </el-form-item>
          <el-form-item label="监控名称">
            <el-input v-model="searchForm.monitor_name" placeholder="搜索监控名称" clearable />
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="searchForm.status" placeholder="全部状态" clearable style="width: 140px">
              <el-option label="运行中" value="running" />
              <el-option label="已暂停" value="paused" />
              <el-option label="已完成" value="completed" />
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleSearch">搜索</el-button>
            <el-button @click="handleReset">重置</el-button>
          </el-form-item>
        </el-form>
        <div class="search-actions">
          <el-button @click="handleAdd" type="primary">新增监控</el-button>
          <el-button @click="handleRefresh" type="success">刷新数据</el-button>
        </div>
      </div>
    </el-card>
    
    <div class="stats-grid">
      <el-card shadow="never" class="stat-card">
        <div class="stat-content">
          <div class="stat-icon" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
            <span class="icon-text">📊</span>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.total_plans }}</div>
            <div class="stat-label">总计划数</div>
          </div>
        </div>
      </el-card>
      
      <el-card shadow="never" class="stat-card">
        <div class="stat-content">
          <div class="stat-icon" style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);">
            <span class="icon-text">✅</span>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.completed_plans }}</div>
            <div class="stat-label">已完成</div>
          </div>
        </div>
      </el-card>
      
      <el-card shadow="never" class="stat-card">
        <div class="stat-content">
          <div class="stat-icon" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
            <span class="icon-text">⚠️</span>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.exception_count }}</div>
            <div class="stat-label">异常数</div>
          </div>
        </div>
      </el-card>
      
      <el-card shadow="never" class="stat-card">
        <div class="stat-content">
          <div class="stat-icon" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
            <span class="icon-text">📈</span>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.progress_rate }}%</div>
            <div class="stat-label">整体进度</div>
          </div>
        </div>
      </el-card>
    </div>
    
    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="monitor_code" label="监控编码" />
        <el-table-column prop="monitor_name" label="监控名称" />
        <el-table-column prop="progress_rate" label="进度(%)" width="120">
          <template #default="{ row }">
            <el-progress :percentage="row.progress_rate" :color="getProgressColor(row.progress_rate)" :stroke-width="12" />
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusTag(row.status)">
              {{ getStatusName(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="exception_count" label="异常数" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.exception_count > 0" type="danger">{{ row.exception_count }}</el-tag>
            <el-tag v-else type="success">{{ row.exception_count }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link @click="handleView(row)">查看</el-button>
              <el-button v-if="row.status === 'running'" type="warning" link @click="handlePause(row)">暂停</el-button>
              <el-button v-if="row.status === 'paused'" type="success" link @click="handleResume(row)">恢复</el-button>
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
    
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form ref="formRef" :model="formData" :rules="rules" label-width="100px">
        <el-form-item label="监控编码" prop="monitor_code">
          <el-input v-model="formData.monitor_code" placeholder="请输入监控编码" />
        </el-form-item>
        <el-form-item label="监控名称" prop="monitor_name">
          <el-input v-model="formData.monitor_name" placeholder="请输入监控名称" />
        </el-form-item>
        <el-form-item label="关联计划">
          <el-select v-model="formData.plan_id" placeholder="请选择关联计划" clearable>
            <el-option v-for="p in plans" :key="p.id" :label="p.plan_code + ' ' + p.plan_name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="监控周期(分钟)">
          <el-input-number v-model="formData.monitor_interval" :min="1" :max="60" />
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

    <el-dialog v-model="detailVisible" title="计划执行监控详情" width="800px">
      <div v-if="detailData">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="监控编码">{{ detailData.monitor_code }}</el-descriptions-item>
          <el-descriptions-item label="监控名称">{{ detailData.monitor_name }}</el-descriptions-item>
          <el-descriptions-item label="进度">{{ detailData.progress_rate }}%</el-descriptions-item>
          <el-descriptions-item label="状态">{{ getStatusName(detailData.status) }}</el-descriptions-item>
          <el-descriptions-item label="异常数">{{ detailData.exception_count }}</el-descriptions-item>
          <el-descriptions-item label="监控周期">{{ detailData.monitor_interval }}分钟</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ detailData.description || '-' }}</el-descriptions-item>
        </el-descriptions>
        
        <el-divider>异常列表</el-divider>
        <el-table :data="detailData.exceptions || []" border>
          <el-table-column prop="exception_code" label="异常编码" />
          <el-table-column prop="exception_type" label="异常类型" />
          <el-table-column prop="message" label="异常信息" />
          <el-table-column prop="occurred_at" label="发生时间" />
          <el-table-column prop="status" label="处理状态">
            <template #default="{ row }">
              <el-tag :type="row.status === 'resolved' ? 'success' : 'danger'">
                {{ row.status === 'resolved' ? '已处理' : '待处理' }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import request from '@/utils/request'

const tableData = ref([])
const plans = ref([])
const stats = reactive({
  total_plans: 0,
  completed_plans: 0,
  exception_count: 0,
  progress_rate: 0
})
const dialogVisible = ref(false)
const detailVisible = ref(false)
const detailData = ref(null)
const dialogTitle = ref('新增计划执行监控')
const isEdit = ref(false)
const currentId = ref(null)
const loading = ref(false)

const searchForm = reactive({
  monitor_code: '',
  monitor_name: '',
  status: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const formData = reactive({
  monitor_code: '',
  monitor_name: '',
  plan_id: null,
  monitor_interval: 5,
  description: ''
})

const rules = {
  monitor_code: [{ required: true, message: '请输入监控编码', trigger: 'blur' }],
  monitor_name: [{ required: true, message: '请输入监控名称', trigger: 'blur' }]
}

const getStatusName = (status) => {
  const statuses = { running: '运行中', paused: '已暂停', completed: '已完成' }
  return statuses[status] || status
}

const getStatusTag = (status) => {
  const tags = { running: 'success', paused: 'warning', completed: 'primary' }
  return tags[status] || 'info'
}

const getProgressColor = (rate) => {
  if (rate >= 90) return '#10b981'
  if (rate >= 60) return '#f59e0b'
  return '#ef4444'
}

const handleSearch = async () => {
  pagination.page = 1
  await fetchData()
}

const handleReset = () => {
  searchForm.monitor_code = ''
  searchForm.monitor_name = ''
  searchForm.status = ''
  handleSearch()
}

const handleAdd = () => {
  isEdit.value = false
  currentId.value = null
  dialogTitle.value = '新增计划执行监控'
  Object.assign(formData, {
    monitor_code: '',
    monitor_name: '',
    plan_id: null,
    monitor_interval: 5,
    description: ''
  })
  dialogVisible.value = true
}

const handleRefresh = async () => {
  await fetchData()
  await fetchStats()
  ElMessage.success('数据已刷新')
}

const handleView = async (row) => {
  const data = await request.get(`/v1/mrp2/monitor/${row.id}`)
  if (data.code === 0) {
    detailData.value = data.data
    detailVisible.value = true
  }
}

const handlePause = async (row) => {
  const data = await request.put(`/v1/mrp2/monitor/${row.id}/pause`)
  if (data.code === 0) {
    ElMessage.success('已暂停')
    fetchData()
  } else {
    ElMessage.error(data.msg || '操作失败')
  }
}

const handleResume = async (row) => {
  const data = await request.put(`/v1/mrp2/monitor/${row.id}/resume`)
  if (data.code === 0) {
    ElMessage.success('已恢复')
    fetchData()
  } else {
    ElMessage.error(data.msg || '操作失败')
  }
}

const handleSave = async () => {
  if (!formData.monitor_code || !formData.monitor_name) {
    ElMessage.warning('请填写必填项')
    return
  }
  
  if (isEdit.value) {
    const data = await request.put(`/v1/mrp2/monitor/${currentId.value}`, formData)
    if (data.code === 0) {
      ElMessage.success('保存成功')
      dialogVisible.value = false
      fetchData()
    } else {
      ElMessage.error(data.msg || '保存失败')
    }
  } else {
    const data = await request.post('/v1/mrp2/monitor/', formData)
    if (data.code === 0) {
      ElMessage.success('保存成功')
      dialogVisible.value = false
      fetchData()
    } else {
      ElMessage.error(data.msg || '保存失败')
    }
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    const data = await request.get('/v1/mrp2/monitor/', { 
      params: { 
        page: pagination.page, 
        page_size: pagination.page_size,
        monitor_code: searchForm.monitor_code,
        monitor_name: searchForm.monitor_name,
        status: searchForm.status
      } 
    })
    tableData.value = data.data?.items || []
    pagination.total = data.data?.total || 0
    pagination.page = data.data?.page || 1
    pagination.page_size = data.data?.page_size || 20
  } catch (error) {
    tableData.value = []
    pagination.total = 0
  }
  loading.value = false
}

const fetchStats = async () => {
  const data = await request.get('/v1/mrp2/monitor/stats')
  if (data.code === 0) {
    Object.assign(stats, data.data)
  }
}

const fetchPlans = async () => {
  const mpsData = await request.get('/v1/mrp2/mps/', { params: { page_size: 50 } })
  const mrpData = await request.get('/v1/mrp2/mrp/', { params: { page_size: 50 } })
  plans.value = [
    ...(mpsData.data?.items || []).map(p => ({ id: p.id, plan_code: p.mps_code, plan_name: p.mps_name })),
    ...(mrpData.data?.items || []).map(p => ({ id: p.id, plan_code: p.mrp_code, plan_name: p.mrp_name }))
  ]
}

onMounted(() => {
  fetchData()
  fetchStats()
  fetchPlans()
})
</script>

<style lang="scss" scoped>
.monitor-index {
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
  
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 20px;
    
    @media (max-width: 1200px) {
      grid-template-columns: repeat(2, 1fr);
    }
    
    @media (max-width: 768px) {
      grid-template-columns: 1fr;
    }
    
    .stat-card {
      .stat-content {
        display: flex;
        align-items: center;
        gap: 16px;
      }
      
      .stat-icon {
        width: 64px;
        height: 64px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        
        .icon-text {
          font-size: 28px;
        }
      }
      
      .stat-info {
        flex: 1;
        
        .stat-value {
          font-size: 28px;
          font-weight: 700;
          color: #333;
        }
        
        .stat-label {
          font-size: 14px;
          color: #999;
          margin-top: 4px;
        }
      }
    }
  }
}
</style>
