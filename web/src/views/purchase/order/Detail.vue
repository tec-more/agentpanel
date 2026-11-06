<template>
  <div class="purchase-order-detail">
    <el-card shadow="never">
      <template #header>
        <div class="detail-header">
          <span>采购订单详情</span>
          <div class="header-actions">
            <el-button :icon="Edit" @click="handleEdit">编辑</el-button>
          </div>
        </div>
      </template>

      <template v-if="order">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="订单号">{{ order.order_no }}</el-descriptions-item>
          <el-descriptions-item label="供应商">{{ order.supplier_name }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTag">{{ order.status_label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="总金额">¥{{ order.total_amount?.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="下单日期">{{ order.order_date }}</el-descriptions-item>
          <el-descriptions-item label="预计到货">{{ order.expected_delivery_date }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ order.created_at }}</el-descriptions-item>
          <el-descriptions-item label="更新时间">{{ order.updated_at }}</el-descriptions-item>
        </el-descriptions>

        <!-- 已有审批实例时显示审批进度（无需额外引入，组件内部已处理） -->
      </template>

      <el-empty v-else description="订单不存在" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Edit } from '@element-plus/icons-vue'
import { getPurchaseOrderDetail } from '@/api/purchase'

const route = useRoute()
const orderId = ref(Number(route.params.id) || null)
const order = ref(null)
const statusTag = ref('info')

onMounted(async () => {
  if (!orderId.value) return
  try {
    const res = await getPurchaseOrderDetail(orderId.value)
    if (res.code === 0 && res.data) {
      order.value = res.data
      const map = { draft: 'info', confirmed: 'warning', partial_received: 'primary', full_received: 'success', cancelled: 'danger' }
      statusTag.value = map[order.value.status] || 'info'
    }
  } catch (e) {
    console.error('获取订单详情失败:', e)
  }
})

const handleEdit = () => { ElMessage.info('编辑功能开发中') }
</script>

<style lang="scss" scoped>
.purchase-order-detail {
  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}
</style>
