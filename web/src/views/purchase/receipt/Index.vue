<template>
  <div class="purchase-receipt-list">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="收货单号">
          <el-input v-model="searchForm.receipt_no" placeholder="请输入收货单号" clearable />
        </el-form-item>
        <el-form-item label="采购单号">
          <el-input v-model="searchForm.order_no" placeholder="请输入采购单号" clearable />
        </el-form-item>
        <el-form-item label="供应商">
          <el-input v-model="searchForm.supplier_name" placeholder="请输入供应商名称" clearable />
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
          <span>采购收货单列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新建收货单</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="receipt_no" label="收货单号" min-width="140" />
        <el-table-column prop="purchase_order_no" label="采购单号" min-width="140" />
        <el-table-column prop="supplier_name" label="供应商" min-width="150" />
        <el-table-column prop="receipt_date" label="收货日期" width="120" />
        <el-table-column prop="warehouse_code" label="仓库" min-width="100" />
        <el-table-column prop="total_amount" label="总金额" width="120">
          <template #default="{ row }">
            <span>{{ row.total_amount.toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="质检结果" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_qualified ? 'success' : 'danger'">
              {{ row.is_qualified ? '合格' : '不合格' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="inspector" label="质检员" min-width="100" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link :icon="View" @click="handleDetail(row)">详情</el-button>
            <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
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
import { Search, Refresh, Plus, View, Delete } from '@element-plus/icons-vue'
import { getPurchaseReceiptList, deletePurchaseReceipt } from '@/api/purchase'

const loading = ref(false)
const tableData = ref([])

const searchForm = reactive({
  receipt_no: '',
  order_no: '',
  supplier_name: '',
  dateRange: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      receipt_no: searchForm.receipt_no,
      order_no: searchForm.order_no,
      supplier_name: searchForm.supplier_name
    }
    if (searchForm.dateRange && searchForm.dateRange.length === 2) {
      params.start_date = searchForm.dateRange[0]
      params.end_date = searchForm.dateRange[1]
    }
    const res = await getPurchaseReceiptList(params)
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) {
    console.error('获取采购收货单列表失败:', e)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.receipt_no = ''; searchForm.order_no = ''; searchForm.supplier_name = ''; searchForm.dateRange = null; handleSearch() }
const handleAdd = () => { ElMessage.info('新建收货单功能开发中') }
const handleDetail = (row) => { ElMessage.info(`收货单详情: ${row.receipt_no}`) }

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除收货单 "${row.receipt_no}" 吗？`, '提示', { type: 'warning' })
    await deletePurchaseReceipt(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {}
}

onMounted(() => { fetchData() })
</script>

<style lang="scss" scoped>
.purchase-receipt-list {
  .search-card { margin-bottom: 16px;
    .search-form { display: flex; flex-wrap: wrap;
      .el-form-item { margin-bottom: 0; margin-right: 16px; }
    }
  }
  .table-card {
    .card-header { display: flex; justify-content: space-between; align-items: center; }
  }
  .pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
}
</style>

