<template>
  <div class="order-detail" v-loading="loading">
    <el-card shadow="never" class="detail-card">
      <template #header>
        <div class="card-header">
          <el-button type="primary" :icon="Back" @click="handleBack">返回列表</el-button>
          <span class="detail-title">订单详情</span>
        </div>
      </template>

      <div v-if="orderInfo" class="detail-content">
        <!-- 基本信息 -->
        <el-descriptions title="订单信息" :column="2" border>
          <el-descriptions-item label="订单ID">{{ orderInfo.id }}</el-descriptions-item>
          <el-descriptions-item label="订单号">{{ orderInfo.order_no }}</el-descriptions-item>
          <el-descriptions-item label="客户名称">{{ orderInfo.customer_name }}</el-descriptions-item>
          <el-descriptions-item label="支付方式">
            <el-tag v-if="orderInfo.payment_method === 'wechat'" type="success">微信支付</el-tag>
            <el-tag v-else-if="orderInfo.payment_method === 'alipay'" type="primary">支付宝</el-tag>
            <el-tag v-else-if="orderInfo.payment_method === 'balance'" type="info">余额支付</el-tag>
            <el-tag v-else type="info">{{ orderInfo.payment_method }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="订单金额">
            <span class="price-text">¥{{ Number(orderInfo.total_amount || 0).toFixed(2) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="优惠金额">
            <span class="price-text discount">-¥{{ Number(orderInfo.discount_amount || 0).toFixed(2) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="实付金额">
            <span class="price-text final">¥{{ Number(orderInfo.final_amount || 0).toFixed(2) }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="订单状态">
            <el-tag v-if="orderInfo.order_status === 'draft'" type="info">草稿</el-tag>
            <el-tag v-else-if="orderInfo.order_status === 'pending'" type="warning">待确认</el-tag>
            <el-tag v-else-if="orderInfo.order_status === 'processing'" type="primary">处理中</el-tag>
            <el-tag v-else-if="orderInfo.order_status === 'shipped'" type="primary">已发货</el-tag>
            <el-tag v-else-if="orderInfo.order_status === 'completed'" type="success">已完成</el-tag>
            <el-tag v-else-if="orderInfo.order_status === 'cancelled'" type="danger">已取消</el-tag>
            <el-tag v-else type="info">{{ orderInfo.order_status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="支付状态">
            <el-tag v-if="orderInfo.payment_status === 'pending'" type="warning">待支付</el-tag>
            <el-tag v-else-if="orderInfo.payment_status === 'paid'" type="success">已支付</el-tag>
            <el-tag v-else-if="orderInfo.payment_status === 'expired'" type="info">已过期</el-tag>
            <el-tag v-else-if="orderInfo.payment_status === 'failed'" type="danger">支付失败</el-tag>
            <el-tag v-else-if="orderInfo.payment_status === 'refunded'" type="info">已退款</el-tag>
            <el-tag v-else type="info">{{ orderInfo.payment_status }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="第三方交易号">{{ orderInfo.trade_no || '暂无' }}</el-descriptions-item>
          <el-descriptions-item label="支付时间">{{ orderInfo.pay_time || '未支付' }}</el-descriptions-item>
          <el-descriptions-item label="过期时间">{{ orderInfo.expire_time }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ orderInfo.created_at }}</el-descriptions-item>
          <el-descriptions-item label="客户端IP">{{ orderInfo.client_ip || '未知' }}</el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ orderInfo.remark || '无' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 订单明细 -->
        <el-divider content-position="left">订单明细</el-divider>
        <el-table :data="orderInfo.items" border stripe>
          <el-table-column prop="id" label="明细ID" width="80" align="center" />
          <el-table-column prop="product_name" label="产品名称" min-width="150" />
          <el-table-column prop="product_type" label="产品类型" width="120" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.product_type === 'membership'" type="success">会员</el-tag>
              <el-tag v-else-if="row.product_type === 'points'" type="primary">积分</el-tag>
              <el-tag v-else-if="row.product_type === 'item'" type="info">商品</el-tag>
              <el-tag v-else type="info">{{ row.product_type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="quantity" label="数量" width="80" align="center" />
          <el-table-column prop="unit_price" label="单价" width="100" align="center">
            <template #default="{ row }">
              ¥{{ Number(row.unit_price || 0).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column prop="total_price" label="小计" width="100" align="center">
            <template #default="{ row }">
              ¥{{ Number(row.total_price || 0).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column prop="extra_info" label="扩展信息" min-width="200">
            <template #default="{ row }">
              <el-tag v-if="row.extra_info && row.extra_info.membership_level_name" type="info" size="small">
                {{ row.extra_info.membership_level_name }}
              </el-tag>
              <pre v-if="row.extra_info" class="extra-info-json">{{ JSON.stringify(row.extra_info, null, 2) }}</pre>
              <span v-else>-</span>
            </template>
          </el-table-column>
        </el-table>

        <!-- 操作按钮 -->
        <div class="action-section">
          <el-button type="danger" :icon="Delete" @click="handleDelete">删除订单</el-button>
        </div>
      </div>

      <el-empty v-else description="暂无数据" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, Delete } from '@element-plus/icons-vue'
import { getOrderDetail, deleteOrder } from '@/api/order'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const orderInfo = ref(null)

const fetchOrderDetail = async () => {
  loading.value = true
  try {
    const res = await getOrderDetail(route.params.id)
    orderInfo.value = res.data
  } catch (e) {
    // 错误已处理
  } finally {
    loading.value = false
  }
}

const handleBack = () => {
  router.back()
}

const handleDelete = async () => {
  try {
    await ElMessageBox.confirm(`确定要删除订单 "${orderInfo.value.order_no}" 吗？`, '提示', {
      type: 'warning',
      confirmButtonText: '确定',
      cancelButtonText: '取消'
    })
    await deleteOrder(route.params.id)
    ElMessage.success('删除成功')
    router.push('/panel/order')
  } catch (e) {
    // 取消或错误
  }
}

onMounted(() => {
  fetchOrderDetail()
})
</script>

<style lang="scss" scoped>
.order-detail {
  .detail-card {
    .card-header {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .detail-title {
      font-size: 18px;
      font-weight: 600;
    }

    .detail-content {
      margin-top: 16px;

      .price-text {
        font-size: 16px;
        font-weight: 600;

        &.final {
          color: #f56c6c;
          font-size: 18px;
        }

        &.discount {
          color: #67c23a;
        }
      }

      .extra-info-json {
        font-size: 12px;
        color: #909399;
        background: #f5f7fa;
        padding: 8px;
        border-radius: 4px;
        margin: 0;
      }
    }

    .action-section {
      margin-top: 24px;
      display: flex;
      gap: 12px;
    }
  }
}
</style>


