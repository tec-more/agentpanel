<template>
  <div class="purchase-order-list">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="采购单号">
          <el-input v-model="searchForm.order_no" placeholder="请输入采购单号" clearable />
        </el-form-item>
        <el-form-item label="供应商">
          <el-input v-model="searchForm.supplier_name" placeholder="请输入供应商名称" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 140px">
            <el-option label="草稿" value="draft" />
            <el-option label="已确认" value="confirmed" />
            <el-option label="部分收货" value="partial_received" />
            <el-option label="已完成" value="full_received" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期范围">
          <el-date-picker
            v-model="searchForm.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>采购订单列表</span>
          <div class="header-actions">
            <el-button type="primary" :icon="Plus" @click="handleAdd">新建采购订单</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="order_no" label="采购单号" min-width="140" />
        <el-table-column prop="supplier_name" label="供应商" min-width="150" />
        <el-table-column label="状态" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTypeMap[row.status] || 'info'">
              {{ row.status_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="order_date" label="下单日期" width="120" />
        <el-table-column prop="expected_delivery_date" label="预计到货" width="120" />
        <el-table-column prop="total_amount" label="总金额" width="120">
          <template #default="{ row }">
            <span>{{ row.total_amount.toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="收货进度" width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.received_quantity > 0 ? (row.received_quantity / row.total_quantity * 100) : 0" :format="(p) => `${row.received_quantity}/${row.total_quantity}`" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="500" fixed="right" align="center">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button type="primary" link :icon="View" @click="handleDetail(row)">详情</el-button>
              <el-button v-if="row.status === 'draft'" type="success" link @click="handleConfirm(row)">确认</el-button>
              <el-button v-if="row.status === 'confirmed'" type="success" link @click="handleReceive(row)">收货</el-button>
              <el-button v-if="['draft', 'confirmed', 'partial_received'].includes(row.status)" type="danger" link @click="handleCancel(row)">取消</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

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
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, View } from '@element-plus/icons-vue'
import { getPurchaseOrderList, confirmPurchaseOrder, cancelPurchaseOrder } from '@/api/purchase'

const loading = ref(false)
const tableData = ref([])

const searchForm = reactive({
  order_no: '',
  supplier_name: '',
  status: null,
  dateRange: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const statusTypeMap = {
  draft: 'info',
  confirmed: 'warning',
  partial_received: 'primary',
  full_received: 'success',
  cancelled: 'danger'
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      order_no: searchForm.order_no,
      supplier_name: searchForm.supplier_name,
      status: searchForm.status
    }
    if (searchForm.dateRange && searchForm.dateRange.length === 2) {
      params.start_date = searchForm.dateRange[0]
      params.end_date = searchForm.dateRange[1]
    }
    const res = await getPurchaseOrderList(params)
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) {
    console.error('获取采购订单列表失败:', e)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.order_no = ''; searchForm.supplier_name = ''; searchForm.status = null; searchForm.dateRange = null; handleSearch() }
const handleAdd = () => { ElMessage.info('新建采购订单功能开发中') }
const handleDetail = (row) => { ElMessage.info(`采购订单详情: ${row.order_no}`) }
const handleReceive = (row) => { ElMessage.info(`采购收货功能开发中: ${row.order_no}`) }

const handleConfirm = async (row) => {
  try {
    await ElMessageBox.confirm(`确定确认采购订单 "${row.order_no}" 吗？`, '提示', { type: 'warning' })
    await confirmPurchaseOrder(row.id)
    ElMessage.success('确认成功')
    fetchData()
  } catch (e) {}
}

const handleCancel = async (row) => {
  try {
    await ElMessageBox.confirm(`确定取消采购订单 "${row.order_no}" 吗？`, '提示', { type: 'warning' })
    await cancelPurchaseOrder(row.id)
    ElMessage.success('取消成功')
    fetchData()
  } catch (e) {}
}

onMounted(() => { fetchData() })
</script>

<style lang="scss" scoped>
.purchase-order-list {
  .search-card { margin-bottom: 16px;
    .search-form { display: flex; flex-wrap: wrap;
      .el-form-item { margin-bottom: 0; margin-right: 16px; }
    }
  }
  .table-card {
    .card-header { display: flex; justify-content: space-between; align-items: center; }
    .header-actions { display: flex; align-items: center; gap: 8px; }
  }
  .pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
  .row-actions {
    display: inline-flex; align-items: center; gap: 4px; flex-wrap: wrap;
    > :deep(.approval-action) { margin-left: 4px; }
  }
}
</style>

