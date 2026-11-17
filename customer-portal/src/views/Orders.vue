<template>
  <el-card shadow="never">
    <template #header>我的订单</template>
    <el-table :data="items" v-loading="loading" size="small" style="width:100%">
      <el-table-column prop="order_no" label="订单号" width="180" />
      <el-table-column prop="final_amount" label="金额" width="110">
        <template #default="{ row }">¥{{ row.final_amount }}</template>
      </el-table-column>
      <el-table-column prop="payment_status" label="支付状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.payment_status === 'paid' ? 'success' : 'warning'" size="small">{{ row.payment_status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="order_status" label="订单状态" width="110" />
      <el-table-column prop="created_at" label="下单时间" />
      <el-table-column label="商品">
        <template #default="{ row }">
          {{ (row.product_details || row.items || []).map(i => i.product_name).join('、') || '—' }}
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && !items.length" description="暂无订单" />
    <div class="pager" v-if="total > pageSize">
      <el-pagination layout="prev, pager, next" :total="total" :page-size="pageSize" v-model:current-page="page" @current-change="load" />
    </div>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiMyOrders } from '@/api'
const items = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)
async function load() {
  loading.value = true
  try {
    const res = await apiMyOrders({ page: page.value, page_size: pageSize })
    items.value = res.data?.items || []
  } catch (e) {} finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.pager { display: flex; justify-content: center; margin-top: 16px; }
</style>
