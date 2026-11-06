<template>
  <div class="order-management">
    <!-- 搜索栏 -->
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="订单号">
          <el-input v-model="searchForm.order_no" placeholder="请输入订单号" clearable />
        </el-form-item>
        <el-form-item label="客户名称">
          <el-input v-model="searchForm.customer_name" placeholder="请输入客户名称" clearable />
        </el-form-item>
        <el-form-item label="产品名称">
          <el-input v-model="searchForm.product_name" placeholder="请输入产品名称" clearable />
        </el-form-item>
        <el-form-item label="订单状态">
          <el-select v-model="searchForm.order_status" placeholder="请选择" clearable style="width: 120px">
            <el-option label="草稿" :value="'draft'" />
            <el-option label="待确认" :value="'pending'" />
            <el-option label="处理中" :value="'processing'" />
            <el-option label="已发货" :value="'shipped'" />
            <el-option label="已完成" :value="'completed'" />
            <el-option label="已取消" :value="'cancelled'" />
          </el-select>
        </el-form-item>
        <el-form-item label="支付状态">
          <el-select v-model="searchForm.payment_status" placeholder="请选择" clearable style="width: 120px">
            <el-option label="待支付" :value="'pending'" />
            <el-option label="已支付" :value="'paid'" />
            <el-option label="支付失败" :value="'failed'" />
            <el-option label="已退款" :value="'refunded'" />
            <el-option label="已过期" :value="'expired'" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>订单列表</span>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="order_no" label="订单号" min-width="150" />
        <el-table-column prop="customer_name" label="客户名称" min-width="120" />
        <el-table-column prop="final_amount" label="订单金额" width="100" align="center">
          <template #default="{ row }">
            ¥{{ Number(row.final_amount || 0).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column label="订单状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.order_status === 'draft'" type="info">
              草稿
            </el-tag>
            <el-tag v-else-if="row.order_status === 'pending'" type="warning">
              待确认
            </el-tag>
            <el-tag v-else-if="row.order_status === 'processing'" type="primary">
              处理中
            </el-tag>
            <el-tag v-else-if="row.order_status === 'shipped'" type="primary">
              已发货
            </el-tag>
            <el-tag v-else-if="row.order_status === 'completed'" type="success">
              已完成
            </el-tag>
            <el-tag v-else-if="row.order_status === 'cancelled'" type="danger">
              已取消
            </el-tag>
            <el-tag v-else type="info">
              {{ row.order_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="支付状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.payment_status === 'pending'" type="warning">
              待支付
            </el-tag>
            <el-tag v-else-if="row.payment_status === 'paid'" type="success">
              已支付
            </el-tag>
            <el-tag v-else-if="row.payment_status === 'failed'" type="danger">
              支付失败
            </el-tag>
            <el-tag v-else-if="row.payment_status === 'refunded'" type="info">
              已退款
            </el-tag>
            <el-tag v-else-if="row.payment_status === 'expired'" type="info">
              已过期
            </el-tag>
            <el-tag v-else type="info">
              {{ row.payment_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="支付方式" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.payment_method === 'wechat'" type="success">
              微信
            </el-tag>
            <el-tag v-else-if="row.payment_method === 'alipay'" type="primary">
              支付宝
            </el-tag>
            <el-tag v-else type="info">
              {{ row.payment_method }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="320" fixed="right" align="center">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button type="primary" link :icon="View" @click="handleDetail(row)">详情</el-button>
              <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, View, Delete } from '@element-plus/icons-vue'
import { getOrderList, deleteOrder } from '@/api/sales'

const router = useRouter()
const loading = ref(false)

const tableData = ref([])

const searchForm = reactive({
  order_no: '',
  customer_name: '',
  order_status: null,
  payment_status: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getOrderList({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    })
    tableData.value = res.data.items
    pagination.total = res.data.total
  } catch (e) {
    // 错误已处理
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.order_no = ''
  searchForm.customer_name = ''
  searchForm.order_status = null
  searchForm.payment_status = null
  handleSearch()
}

const handleDetail = (row) => {
  router.push(`/panel/order/${row.id}`)
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除订单 "${row.order_no}" 吗？`, '提示', {
      type: 'warning'
    })
    await deleteOrder(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    // 取消或错误
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style lang="scss" scoped>
.order-management {
  .search-card {
    margin-bottom: 16px;

    .search-form {
      display: flex;
      flex-wrap: wrap;

      .el-form-item {
        margin-bottom: 0;
        margin-right: 16px;
      }
    }
  }

  .table-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .header-actions {
      display: flex; align-items: center; gap: 8px;
    }
  }

  .pagination-wrapper {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }

  .row-actions {
    display: inline-flex; align-items: center; gap: 4px; flex-wrap: wrap;
  }
}
</style>

