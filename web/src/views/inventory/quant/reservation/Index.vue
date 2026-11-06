<template>
  <div class="reservation-list">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="产品编码">
          <el-input v-model="searchForm.product_code" placeholder="请输入产品编码" clearable />
        </el-form-item>
        <el-form-item label="库位">
          <el-input v-model="searchForm.location_name" placeholder="请输入库位" clearable />
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
          <span>库存预留列表</span>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="product_code" label="产品编码" min-width="120" />
        <el-table-column prop="product_name" label="产品名称" min-width="150" />
        <el-table-column prop="location_name" label="库位" min-width="120" />
        <el-table-column prop="reserved_quantity" label="预留数量" width="120" align="center" />
        <el-table-column prop="move_line_id" label="关联移动明细ID" width="140" align="center" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
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
import { Search, Refresh } from '@element-plus/icons-vue'
import { getReservationList } from '@/api/inventory'

const loading = ref(false)
const tableData = ref([])

const searchForm = reactive({
  product_code: '',
  location_name: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getReservationList({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) {
    console.error('获取预留列表失败:', e)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.product_code = ''
  searchForm.location_name = ''
  handleSearch()
}

onMounted(() => {
  fetchData()
})
</script>

<style lang="scss" scoped>
.reservation-list {
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
  }
  .pagination-wrapper {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>


