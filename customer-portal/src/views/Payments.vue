<template>
  <el-card shadow="never">
    <template #header>支付记录</template>
    <el-table :data="items" v-loading="loading" size="small" style="width:100%">
      <el-table-column prop="transaction_id" label="交易号" width="200" show-overflow-tooltip />
      <el-table-column prop="order_no" label="订单号" width="180" />
      <el-table-column prop="transaction_type" label="方式" width="90">
        <template #default="{ row }">{{ row.transaction_type === 'wechat' ? '微信' : row.transaction_type === 'alipay' ? '支付宝' : row.transaction_type }}</template>
      </el-table-column>
      <el-table-column prop="amount" label="金额" width="110">
        <template #default="{ row }">¥{{ row.amount }}</template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : row.status === 'refunded' ? 'info' : 'warning'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="processed_at" label="处理时间" />
    </el-table>
    <el-empty v-if="!loading && !items.length" description="暂无支付记录" />
    <div class="pager" v-if="total > pageSize">
      <el-pagination layout="prev, pager, next" :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="load" />
    </div>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiMyPayments } from '@/api'
const items = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)
async function load() {
  loading.value = true
  try {
    const res = await apiMyPayments({ page: page.value, page_size: pageSize })
    items.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch (e) {} finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.pager { display: flex; justify-content: center; margin-top: 16px; }
</style>
