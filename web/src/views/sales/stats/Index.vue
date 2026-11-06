<template>
  <div class="sales-stats">
    <el-card shadow="never" class="stats-card">
      <template #header>
        <div class="card-header">
          <span>销售概览</span>
        </div>
      </template>

      <div class="stats-grid">
        <el-statistic title="总订单数" :value="overview.total_orders" class="stat-item">
          <template #suffix>
            <span class="suffix">单</span>
          </template>
        </el-statistic>
        <el-statistic title="总销售额" :value="overview.total_amount" class="stat-item">
          <template #prefix>
            <span class="prefix">¥</span>
          </template>
        </el-statistic>
        <el-statistic title="今日订单" :value="overview.today_orders" class="stat-item">
          <template #suffix>
            <span class="suffix">单</span>
          </template>
        </el-statistic>
        <el-statistic title="今日销售额" :value="overview.today_amount" class="stat-item">
          <template #prefix>
            <span class="prefix">¥</span>
          </template>
        </el-statistic>
        <el-statistic title="待支付" :value="overview.pending_orders" class="stat-item">
          <template #suffix>
            <span class="suffix">单</span>
          </template>
        </el-statistic>
        <el-statistic title="已取消" :value="overview.cancelled_orders" class="stat-item">
          <template #suffix>
            <span class="suffix">单</span>
          </template>
        </el-statistic>
      </div>
    </el-card>

    <el-card shadow="never" class="chart-card">
      <template #header>
        <div class="card-header">
          <span>畅销产品排行</span>
        </div>
      </template>

      <el-table v-loading="loading" :data="topProducts" border stripe>
        <el-table-column prop="product_name" label="产品名称" min-width="150" />
        <el-table-column prop="product_type" label="产品类型" width="100" />
        <el-table-column prop="total_quantity" label="销售数量" width="100" align="center" />
        <el-table-column prop="total_sales" label="销售额" width="120" align="center">
          <template #default="{ row }">
            ¥{{ Number(row.total_sales || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="order_count" label="订单数" width="100" align="center" />
      </el-table>
    </el-card>

    <el-card shadow="never" class="chart-card">
      <template #header>
        <div class="card-header">
          <span>客户消费排行</span>
        </div>
      </template>

      <el-table v-loading="loading" :data="topCustomers" border stripe>
        <el-table-column prop="customer_name" label="客户名称" min-width="120" />
        <el-table-column prop="customer_phone" label="联系电话" min-width="130" />
        <el-table-column prop="total_spent" label="消费金额" width="120" align="center">
          <template #default="{ row }">
            ¥{{ Number(row.total_spent || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="order_count" label="订单数" width="100" align="center" />
      </el-table>
    </el-card>

    <el-card shadow="never" class="chart-card">
      <template #header>
        <div class="card-header">
          <span>支付方式统计</span>
        </div>
      </template>

      <div class="payment-stats">
        <div
          v-for="(stat, method) in paymentStats.methods"
          :key="method"
          class="payment-item"
        >
          <div class="payment-label">
            <span>{{ getPaymentLabel(method) }}</span>
            <span class="payment-value">¥{{ stat.amount.toFixed(2) }} ({{ stat.percentage }}%)</span>
          </div>
          <div class="payment-bar">
            <div
              class="payment-fill"
              :style="{ width: stat.percentage + '%' }"
            ></div>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { ElStatistic } from 'element-plus'
import {
  getSalesOverview,
  getTopProducts,
  getTopCustomers,
  getPaymentMethodStats
} from '@/api/sales'

const loading = ref(false)

const overview = reactive({
  total_orders: 0,
  total_amount: 0,
  total_items: 0,
  today_orders: 0,
  today_amount: 0,
  pending_orders: 0,
  cancelled_orders: 0
})

const topProducts = ref([])
const topCustomers = ref([])
const paymentStats = reactive({
  total_amount: 0,
  total_orders: 0,
  methods: {}
})

const getPaymentLabel = (method) => {
  const labels = {
    wechat: '微信支付',
    alipay: '支付宝',
    balance: '余额支付'
  }
  return labels[method] || method
}

const fetchOverview = async () => {
  try {
    const res = await getSalesOverview()
    Object.assign(overview, res.data)
  } catch (e) {
    ElMessage.error('获取销售概览失败')
  }
}

const fetchTopProducts = async () => {
  try {
    const res = await getTopProducts(10)
    topProducts.value = res.data
  } catch (e) {
    ElMessage.error('获取畅销产品失败')
  }
}

const fetchTopCustomers = async () => {
  try {
    const res = await getTopCustomers(10)
    topCustomers.value = res.data
  } catch (e) {
    ElMessage.error('获取客户排行失败')
  }
}

const fetchPaymentStats = async () => {
  try {
    const res = await getPaymentMethodStats()
    Object.assign(paymentStats, res.data)
  } catch (e) {
    ElMessage.error('获取支付方式统计失败')
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    await Promise.all([
      fetchOverview(),
      fetchTopProducts(),
      fetchTopCustomers(),
      fetchPaymentStats()
    ])
  } catch (e) {
    // 错误已处理
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style lang="scss" scoped>
.sales-stats {
  .stats-card {
    margin-bottom: 16px;

    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
    }

    .stat-item {
      text-align: center;
      padding: 16px;
      background: #f8fafc;
      border-radius: 8px;

      :deep(.el-statistic__label) {
        font-size: 14px;
        color: #64748b;
      }

      :deep(.el-statistic__content) {
        font-size: 24px;
        font-weight: bold;
        color: #1e293b;
      }

      .prefix,
      .suffix {
        font-size: 16px;
        color: #64748b;
      }
    }
  }

  .chart-card {
    margin-bottom: 16px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
  }

  .payment-stats {
    .payment-item {
      margin-bottom: 12px;

      .payment-label {
        display: flex;
        justify-content: space-between;
        margin-bottom: 4px;
        font-size: 14px;

        .payment-value {
          font-weight: bold;
        }
      }

      .payment-bar {
        height: 8px;
        background: #e2e8f0;
        border-radius: 4px;
        overflow: hidden;

        .payment-fill {
          height: 100%;
          background: linear-gradient(90deg, #3b82f6, #10b981);
          border-radius: 4px;
          transition: width 0.3s ease;
        }
      }
    }
  }
}
</style>


