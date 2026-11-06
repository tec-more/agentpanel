<template>
  <div class="payments-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>支付记录</span>
        </div>
      </template>

      <!-- 搜索表单 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="订单号">
          <el-input v-model="searchForm.trade_no" placeholder="请输入订单号（支持模糊搜索）" clearable style="width: 200px" />
        </el-form-item>
        <el-form-item label="支付方式">
          <el-select v-model="searchForm.payment_method" placeholder="请选择支付方式" clearable style="width: 150px">
            <el-option label="全部" :value="null" />
            <el-option label="微信支付" value="wxpay" />
            <el-option label="支付宝" value="alipay" />
            <el-option label="七相-微信" value="qixiang_wxpay" />
            <el-option label="七相-支付宝" value="qixiang_alipay" />
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
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="order_no" label="商户订单号" min-width="180">
          <template #default="{ row }">
            <span v-if="row.order_no" class="order-no">{{ row.order_no }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="qixiang_trade_no" label="订单号" min-width="180">
          <template #default="{ row }">
            <span v-if="row.qixiang_trade_no" class="trade-no">{{ row.qixiang_trade_no }}</span>
            <span v-else-if="row.transaction_id" class="trade-no">{{ row.transaction_id }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="amount" label="金额" width="100" align="center">
          <template #default="{ row }">
            <span class="amount">¥{{ Number(row.amount || 0).toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="支付方式" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.payment_method_display" :type="row.payment_method_tag || 'info'">
              {{ row.payment_method_display }}
            </el-tag>
            <span v-else class="text-muted">{{ getPaymentMethodLabel(row.transaction_type) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="processed_at" label="处理时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.processed_at) }}
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import { getPaymentTransactions } from '@/api/customer'

// 响应式数据
const loading = ref(false)
const tableData = ref([])

const searchForm = reactive({
  trade_no: '',
  payment_method: null
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
    const res = await getPaymentTransactions({
      page: pagination.page,
      page_size: pagination.pageSize,
      trade_no: searchForm.trade_no,
      payment_method: searchForm.payment_method
    })

    if (res.success) {
      tableData.value = res.data.items || []
      pagination.total = res.data.total || 0
    } else {
      ElMessage.error(res.msg || '获取数据失败')
    }
  } catch (e) {
    ElMessage.error('获取数据失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

const handleReset = () => {
  searchForm.trade_no = ''
  searchForm.payment_method = null
  fetchData()
}

const getPaymentMethodLabel = (method) => {
  const labels = {
    wechat: '微信支付',
    wxpay: '微信支付',
    alipay: '支付宝',
    qixiang_wxpay: '七相-微信',
    qixiang_alipay: '七相-支付宝'
  }
  return labels[method] || method || '-'
}

const getStatusLabel = (status) => {
  const labels = {
    success: '成功',
    pending: '处理中',
    failed: '失败',
    refunded: '已退款'
  }
  return labels[status] || status
}

const getStatusType = (status) => {
  const types = {
    success: 'success',
    pending: 'warning',
    failed: 'danger',
    refunded: 'info'
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
.payments-container {
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

/* 样式优化 */
.order-no, .trade-no {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #606266;
}

.amount {
  font-weight: 600;
  color: #f56c6c;
}

.text-muted {
  color: #909399;
}
</style>


