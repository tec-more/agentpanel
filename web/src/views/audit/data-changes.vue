﻿<template>
  <div class="data-changes">
    <!-- 搜索栏 -->
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="表名">
          <el-input v-model="searchForm.table_name" placeholder="请输入表名" clearable />
        </el-form-item>
        <el-form-item label="记录ID">
          <el-input v-model="searchForm.record_id" placeholder="请输入记录ID" clearable />
        </el-form-item>
        <el-form-item label="变更类型">
          <el-select v-model="searchForm.change_type" placeholder="请选择" clearable style="width: 120px">
            <el-option label="CREATE" value="create" />
            <el-option label="UPDATE" value="update" />
            <el-option label="DELETE" value="delete" />
          </el-select>
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="searchForm.username" placeholder="请输入用户名" clearable />
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            value-format="YYYY-MM-DD HH:mm:ss"
            style="width: 360px"
          />
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
          <span>数据变更日志列表</span>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="trace_id" label="Trace ID" width="200" show-overflow-tooltip />
        <el-table-column prop="table_name" label="表名" width="150" />
        <el-table-column prop="record_id" label="记录ID" width="150" />
        <el-table-column label="变更类型" width="120" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="getChangeTypeTagType(row.change_type)">
              {{ row.change_type?.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="ip_address" label="IP地址" width="140" />
        <el-table-column prop="business_no" label="业务流水号" width="150" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" link :icon="View" @click="handleDetail(row)">详情</el-button>
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

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailDialogVisible" title="数据变更日志详情" width="900px">
      <el-descriptions v-if="currentLog" :column="1" border>
        <el-descriptions-item label="ID">{{ currentLog.id }}</el-descriptions-item>
        <el-descriptions-item label="Trace ID">{{ currentLog.trace_id }}</el-descriptions-item>
        <el-descriptions-item label="表名">{{ currentLog.table_name }}</el-descriptions-item>
        <el-descriptions-item label="记录ID">{{ currentLog.record_id }}</el-descriptions-item>
        <el-descriptions-item label="变更类型">
          <el-tag size="small" :type="getChangeTypeTagType(currentLog.change_type)">
            {{ currentLog.change_type?.toUpperCase() }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="变更前数据">
          <pre v-if="currentLog.before_data">{{ JSON.stringify(currentLog.before_data, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="变更后数据">
          <pre v-if="currentLog.after_data">{{ JSON.stringify(currentLog.after_data, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="变更字段">
          <el-tag v-for="field in currentLog.changed_fields" :key="field" size="small" style="margin-right: 4px; margin-bottom: 4px;">
            {{ field }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="用户名">{{ currentLog.username }}</el-descriptions-item>
        <el-descriptions-item label="IP地址">{{ currentLog.ip_address }}</el-descriptions-item>
        <el-descriptions-item label="User-Agent">{{ currentLog.user_agent }}</el-descriptions-item>
        <el-descriptions-item label="业务流水号">{{ currentLog.business_no }}</el-descriptions-item>
        <el-descriptions-item label="备注">{{ currentLog.remark }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ currentLog.created_at }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ currentLog.updated_at }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRoute } from 'vue-router'
import { Search, Refresh, View } from '@element-plus/icons-vue'
import request from '@/utils/request'

const route = useRoute()

const loading = ref(false)
const detailDialogVisible = ref(false)
const currentLog = ref(null)

const tableData = ref([])
const dateRange = ref([])

const searchForm = reactive({
  table_name: '',
  record_id: '',
  change_type: null,
  username: ''
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const getChangeTypeTagType = (changeType) => {
  const types = {
    create: 'success',
    update: 'primary',
    delete: 'danger'
  }
  return types[changeType] || ''
}

const fetchData = async () => {
  loading.value = true
  try {
    const params = {
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    }
    if (dateRange.value && dateRange.value.length === 2) {
      params.start_time = dateRange.value[0]
      params.end_time = dateRange.value[1]
    }
    const res = await request.get('/v1/audit/data-changes/list', { params })
    tableData.value = res.data.items || res.data || []
    pagination.total = res.data.total || tableData.value.length
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
  searchForm.table_name = ''
  searchForm.record_id = ''
  searchForm.change_type = null
  searchForm.username = ''
  dateRange.value = []
  handleSearch()
}

const handleDetail = (row) => {
  currentLog.value = row
  detailDialogVisible.value = true
}

// B1+：深链预筛（如 /panel/audit/data-changes?table_name=resource_grant），
// 仅预填表名并自动查询一次，不影响其他入口的默认行为
const initialTableName = typeof route.query.table_name === 'string' ? route.query.table_name.trim() : ''
if (initialTableName) {
  searchForm.table_name = initialTableName
}

fetchData()
</script>

<style lang="scss" scoped>
.data-changes {
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

  .action-buttons {
    display: flex;
    justify-content: flex-start;
    align-items: center;
    gap: 4px;
  }
}
</style>


