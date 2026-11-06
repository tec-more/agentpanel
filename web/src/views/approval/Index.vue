<template>
  <div class="approval-center">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-cards">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card" @click="handleTabChange('my_todo')">
          <div class="stat-content">
            <div class="stat-icon todo">
              <el-icon><Bell /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.todo }}</div>
              <div class="stat-label">待我审批</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card" @click="handleTabChange('my_done')">
          <div class="stat-content">
            <div class="stat-icon done">
              <el-icon><Check /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.done }}</div>
              <div class="stat-label">我已审批</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card" @click="handleTabChange('my_initiated')">
          <div class="stat-content">
            <div class="stat-icon initiated">
              <el-icon><Promotion /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.initiated }}</div>
              <div class="stat-label">我发起的</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon total">
              <el-icon><Document /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.total }}</div>
              <div class="stat-label">全部审批</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Tab 切换 -->
    <el-card shadow="never" class="table-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="待我审批" name="my_todo" />
        <el-tab-pane label="我已审批" name="my_done" />
        <el-tab-pane label="我发起的" name="my_initiated" />
      </el-tabs>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="title" label="审批标题" min-width="180" show-overflow-tooltip />
        <el-table-column prop="business_type" label="业务类型" width="120">
          <template #default="{ row }">{{ row.business_type || '通用' }}</template>
        </el-table-column>
        <el-table-column prop="applicant_name" label="申请人" width="100">
          <template #default="{ row }">
            {{ row.applicant?.alias || row.applicant?.username || '未知' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="current_node" label="当前节点" width="120">
          <template #default="{ row }">{{ row.current_node || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleView(row)">查看</el-button>
            <el-button
              v-if="activeTab === 'my_todo' && row.status === 'pending'"
              type="success" link @click="handleApprove(row)"
            >审批</el-button>
            <el-button
              v-if="activeTab === 'my_initiated' && row.status === 'pending'"
              type="danger" link @click="handleCancel(row)"
            >撤销</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :page-sizes="[10, 20, 50]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>

    <!-- 审批详情抽屉 -->
    <el-drawer v-model="detailVisible" :title="detailTitle" size="60%" destroy-on-close>
      <InstanceDetail
        v-if="detailVisible && currentInstanceId"
        :instance-id="currentInstanceId"
        @refresh="fetchData"
      />
    </el-drawer>

    <!-- 审批操作对话框 -->
    <el-dialog v-model="approveVisible" title="审批操作" width="500px">
      <el-form :model="approveForm" label-width="80px">
        <el-form-item label="审批结果">
          <el-radio-group v-model="approveForm.approved">
            <el-radio :value="true">通过</el-radio>
            <el-radio :value="false">拒绝</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="审批意见">
          <el-input v-model="approveForm.comment" type="textarea" :rows="3" placeholder="请输入审批意见" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="approveVisible = false">取消</el-button>
        <el-button type="primary" @click="submitApprove">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getInstanceList, cancelInstance, getMyTasks, approveTask } from '@/api/approval'
import InstanceDetail from './InstanceDetail.vue'

const loading = ref(false)
const activeTab = ref('my_todo')
const tableData = ref([])
const detailVisible = ref(false)
const detailTitle = ref('')
const currentInstanceId = ref(null)
const approveVisible = ref(false)
const approveForm = reactive({ taskId: null, approved: true, comment: '' })

const pagination = reactive({ page: 1, page_size: 10, total: 0 })
const stats = reactive({ todo: 0, done: 0, initiated: 0, total: 0 })

const statusMap = {
  pending: { label: '审批中', type: 'warning' },
  approved: { label: '已通过', type: 'success' },
  rejected: { label: '已拒绝', type: 'danger' },
  cancelled: { label: '已撤销', type: 'info' }
}

const getStatusLabel = (status) => statusMap[status]?.label || status
const getStatusType = (status) => statusMap[status]?.type || 'info'

const fetchData = async () => {
  loading.value = true
  try {
    const params = { ...pagination, scope: activeTab.value }
    const res = await getInstanceList(params)
    if (res.code === 0 || res.code === 200 || res.success) {
      tableData.value = res.data.items || []
      pagination.total = res.data.total || 0
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  try {
    const todoRes = await getMyTasks({ status: 'pending', page: 1, page_size: 1 })
    if (todoRes.code === 0 || todoRes.code === 200) {
      stats.todo = todoRes.data.total || 0
    }
    const initiatedRes = await getInstanceList({ scope: 'my_initiated', page: 1, page_size: 1 })
    if (initiatedRes.code === 0 || initiatedRes.code === 200) {
      stats.initiated = initiatedRes.data.total || 0
    }
    const doneRes = await getInstanceList({ scope: 'my_done', page: 1, page_size: 1 })
    if (doneRes.code === 0 || doneRes.code === 200) {
      stats.done = doneRes.data.total || 0
    }
    stats.total = stats.todo + stats.done + stats.initiated
  } catch (e) {
    console.error(e)
  }
}

const handleTabChange = (tab) => {
  activeTab.value = tab
  pagination.page = 1
  fetchData()
}

const handleView = (row) => {
  currentInstanceId.value = row.id
  detailTitle.value = `审批详情 - ${row.title}`
  detailVisible.value = true
}

const handleApprove = async (row) => {
  // 获取待办任务ID
  const tasks = await getMyTasks({ status: 'pending', page: 1, page_size: 100 })
  if (tasks.code === 0 || tasks.code === 200) {
    const task = tasks.data.items.find(t => t.instance_id === row.id)
    if (task) {
      approveForm.taskId = task.id
      approveForm.approved = true
      approveForm.comment = ''
      approveVisible.value = true
    }
  }
}

const submitApprove = async () => {
  try {
    const res = await approveTask(approveForm.taskId, {
      approved: approveForm.approved,
      comment: approveForm.comment
    })
    if (res.code === 0 || res.code === 200 || res.success) {
      ElMessage.success('审批成功')
      approveVisible.value = false
      fetchData()
      fetchStats()
    }
  } catch (e) {
    console.error(e)
  }
}

const handleCancel = async (row) => {
  try {
    await ElMessageBox.confirm('确定要撤销该审批吗？', '提示', { type: 'warning' })
    const res = await cancelInstance(row.id)
    if (res.code === 0 || res.code === 200 || res.success) {
      ElMessage.success('撤销成功')
      fetchData()
      fetchStats()
    }
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

onMounted(() => {
  fetchData()
  fetchStats()
})
</script>

<style scoped lang="scss">
.approval-center {
  padding: 16px;
}

.stat-cards {
  margin-bottom: 16px;
}

.stat-card {
  cursor: pointer;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  }
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: #fff;

  &.todo { background: linear-gradient(135deg, #409EFF, #66b1ff); }
  &.done { background: linear-gradient(135deg, #67C23A, #85ce61); }
  &.initiated { background: linear-gradient(135deg, #E6A23C, #ebb563); }
  &.total { background: linear-gradient(135deg, #909399, #a6a9ad); }
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.table-card {
  margin-top: 16px;
}

.pagination-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
