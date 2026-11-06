<template>
  <div class="picking-list">
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="调拨单号">
          <el-input v-model="searchForm.picking_code" placeholder="请输入调拨单号" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.state" placeholder="请选择" clearable style="width: 120px">
            <el-option label="草稿" value="draft" />
            <el-option label="已确认" value="confirmed" />
            <el-option label="已预留" value="assigned" />
            <el-option label="部分完成" value="partially_available" />
            <el-option label="已完成" value="done" />
            <el-option label="已取消" value="cancel" />
          </el-select>
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
          <span>出库调拨列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新建调拨单</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="picking_code" label="调拨单号" min-width="140" />
        <el-table-column prop="picking_type_name" label="调拨类型" min-width="120" />
        <el-table-column prop="location_name" label="源库位" min-width="120" />
        <el-table-column prop="location_dest_name" label="目标库位" min-width="120" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="stateTypeMap[row.state] || 'info'">
              {{ stateMap[row.state] || row.state }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="scheduled_date" label="计划日期" width="180" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="280" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link :icon="View" @click="handleDetail(row)">详情</el-button>
            <el-button v-if="row.state === 'draft'" type="success" link @click="handleConfirm(row)">确认</el-button>
            <el-button v-if="row.state === 'confirmed'" type="warning" link @click="handleAssign(row)">预留</el-button>
            <el-button v-if="row.state === 'assigned'" type="success" link @click="handleDo(row)">完成</el-button>
            <el-button v-if="['draft', 'confirmed', 'assigned'].includes(row.state)" type="danger" link @click="handleCancel(row)">取消</el-button>
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
import {
  getPickingList,
  confirmPicking,
  assignPicking,
  doPicking,
  cancelPicking
} from '@/api/inventory'

const loading = ref(false)
const tableData = ref([])

const searchForm = reactive({
  picking_code: '',
  state: null,
  picking_type: 'outgoing'
})

const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const stateMap = {
  draft: '草稿',
  confirmed: '已确认',
  assigned: '已预留',
  partially_available: '部分完成',
  done: '已完成',
  cancel: '已取消'
}

const stateTypeMap = {
  draft: 'info',
  confirmed: 'warning',
  assigned: 'primary',
  partially_available: 'success',
  done: 'success',
  cancel: 'danger'
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getPickingList({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    })
    tableData.value = res.data.items || []
    pagination.total = res.data.total || 0
  } catch (e) { console.error('获取调拨单列表失败:', e) }
  finally { loading.value = false }
}

const handleSearch = () => { pagination.page = 1; fetchData() }
const handleReset = () => { searchForm.picking_code = ''; searchForm.state = null; handleSearch() }
const handleAdd = () => { ElMessage.info('请在详情页创建调拨单') }
const handleDetail = (row) => { ElMessage.info(`调拨单详情: ${row.picking_code}`) }

const handleConfirm = async (row) => {
  try {
    await ElMessageBox.confirm(`确定确认调拨单 "${row.picking_code}" 吗？`, '提示', { type: 'warning' })
    await confirmPicking(row.id); ElMessage.success('确认成功'); fetchData()
  } catch (e) {}
}
const handleAssign = async (row) => {
  try {
    await ElMessageBox.confirm(`确定预留调拨单 "${row.picking_code}" 吗？`, '提示', { type: 'warning' })
    await assignPicking(row.id); ElMessage.success('预留成功'); fetchData()
  } catch (e) {}
}
const handleDo = async (row) => {
  try {
    await ElMessageBox.confirm(`确定完成调拨单 "${row.picking_code}" 吗？`, '提示', { type: 'warning' })
    await doPicking(row.id); ElMessage.success('完成成功'); fetchData()
  } catch (e) {}
}
const handleCancel = async (row) => {
  try {
    await ElMessageBox.confirm(`确定取消调拨单 "${row.picking_code}" 吗？`, '提示', { type: 'warning' })
    await cancelPicking(row.id); ElMessage.success('取消成功'); fetchData()
  } catch (e) {}
}

onMounted(() => { fetchData() })
</script>

<style lang="scss" scoped>
.picking-list {
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


