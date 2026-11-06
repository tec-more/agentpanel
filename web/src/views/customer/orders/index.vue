<template>
  <div class="customer-orders-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>订单管理</span>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            新建订单
          </el-button>
        </div>
      </template>

      <!-- 搜索表单 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="订单号">
          <el-input v-model="searchForm.order_no" placeholder="请输入订单号" clearable />
        </el-form-item>
        <el-form-item label="支付状态">
          <el-select v-model="searchForm.payment_status" placeholder="请选择状态" clearable>
            <el-option label="全部" :value="null" />
            <el-option label="待支付" value="pending" />
            <el-option label="已支付" value="paid" />
            <el-option label="已取消" value="cancelled" />
            <el-option label="已过期" value="expired" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchData">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="handleReset">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 数据表格 -->
      <el-table :data="tableData" style="width: 100%" v-loading="loading" border>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="order_no" label="订单号" width="200" />
        <el-table-column prop="customer_id" label="客户ID" width="100" />
        <el-table-column prop="membership_level_id" label="会员等级ID" width="120" />
        <el-table-column prop="amount" label="金额" width="100">
          <template #default="{ row }">
            ¥{{ row.amount }}
          </template>
        </el-table-column>
        <el-table-column prop="total_hours" label="总小时数" width="100" />
        <el-table-column prop="payment_method" label="支付方式" width="100">
          <template #default="{ row }">
            {{ getPaymentMethodLabel(row.payment_method) }}
          </template>
        </el-table-column>
        <el-table-column prop="payment_status" label="支付状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.payment_status)">
              {{ getStatusLabel(row.payment_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="expire_time" label="过期时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.expire_time) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="handleView(row)">
              查看
            </el-button>
            <el-button
              v-if="row.payment_status === 'pending'"
              type="warning"
              size="small"
              @click="handleCancel(row)"
            >
              取消
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>

    <!-- 查看详情对话框 -->
    <el-dialog v-model="detailDialogVisible" title="订单详情" width="800px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="订单号">{{ currentOrder.order_no }}</el-descriptions-item>
        <el-descriptions-item label="客户ID">{{ currentOrder.customer_id }}</el-descriptions-item>
        <el-descriptions-item label="会员等级ID">{{ currentOrder.membership_level_id }}</el-descriptions-item>
        <el-descriptions-item label="金额">¥{{ currentOrder.amount }}</el-descriptions-item>
        <el-descriptions-item label="总小时数">{{ currentOrder.total_hours }}</el-descriptions-item>
        <el-descriptions-item label="支付方式">{{ getPaymentMethodLabel(currentOrder.payment_method) }}</el-descriptions-item>
        <el-descriptions-item label="支付状态">
          <el-tag :type="getStatusType(currentOrder.payment_status)">
            {{ getStatusLabel(currentOrder.payment_status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDateTime(currentOrder.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="过期时间">{{ formatDateTime(currentOrder.expire_time) }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{ currentOrder.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh } from '@element-plus/icons-vue'
import { getOrderList } from '@/api/order'

// 响应式数据
const loading = ref(false)
const tableData = ref([])
const detailDialogVisible = ref(false)
const currentOrder = ref({})

const searchForm = reactive({
  order_no: '',
  payment_status: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

// 方法
const fetchData = async () => {
  loading.value = true
  try {
    const res = await getOrderList({
      page: pagination.page,
      page_size: pagination.pageSize,
      order_no: searchForm.order_no || undefined,
      payment_status: searchForm.payment_status || undefined
    })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) {
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

const handleReset = () => {
  searchForm.order_no = ''
  searchForm.payment_status = null
  fetchData()
}

const handleCreate = () => {
  ElMessage.info('创建订单功能待实现')
}

const handleView = (row) => {
  currentOrder.value = row
  detailDialogVisible.value = true
}

const handleCancel = (row) => {
  ElMessageBox.confirm('确定要取消该订单吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    ElMessage.success('订单已取消')
    fetchData()
  })
}

const getPaymentMethodLabel = (method) => {
  const labels = {
    wechat: '微信支付',
    alipay: '支付宝',
    balance: '余额支付'
  }
  return labels[method] || method
}

const getStatusLabel = (status) => {
  const labels = {
    pending: '待支付',
    paid: '已支付',
    cancelled: '已取消',
    expired: '已过期',
    failed: '支付失败'
  }
  return labels[status] || status
}

const getStatusType = (status) => {
  const types = {
    pending: 'warning',
    paid: 'success',
    cancelled: 'info',
    expired: 'danger',
    failed: 'danger'
  }
  return types[status] || 'info'
}

const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.customer-orders-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}
</style>


