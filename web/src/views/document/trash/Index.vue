<template>
  <div class="document-trash">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>回收站</span>
          <div class="header-actions">
            <el-button type="danger" :icon="Delete" @click="handleEmpty" :disabled="!tableData.length">
              清空回收站
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="tableData" v-loading="loading" stripe border>
        <el-table-column prop="title" label="文档标题" min-width="200" />
        <el-table-column prop="file_name" label="文件名" min-width="150" />
        <el-table-column prop="file_type" label="类型" width="80" />
        <el-table-column prop="version" label="版本" width="70" />
        <el-table-column prop="updated_at" label="删除时间" width="170">
          <template #default="{ row }">
            {{ formatDate(row.updated_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="success" size="small" @click="handleRestore(row)">
              恢复
            </el-button>
            <el-button link type="danger" size="small" @click="handlePermanentDelete(row)">
              永久删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="fetchList"
          @current-change="fetchList"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Delete } from '@element-plus/icons-vue'
import { getTrashList, permanentDeleteDocument, batchRestoreDocuments } from '@/api/document'

const loading = ref(false)
const tableData = ref([])

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const fetchList = async () => {
  loading.value = true
  try {
    const res = await getTrashList({
      page: pagination.page,
      page_size: pagination.page_size
    })
    if (res.code === 0) {
      tableData.value = res.data.items
      pagination.total = res.data.total
    }
  } catch (e) {
    ElMessage.error('获取回收站失败')
  } finally {
    loading.value = false
  }
}

const handleRestore = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要恢复「${row.title}」吗？`, '确认恢复')
    const res = await batchRestoreDocuments({ document_ids: [row.id] })
    if (res.code === 0 && res.data.restored_count > 0) {
      ElMessage.success('恢复成功')
      fetchList()
    } else {
      ElMessage.error('恢复失败')
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('恢复失败')
  }
}

const handlePermanentDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要永久删除「${row.title}」吗？此操作不可恢复！`,
      '确认永久删除',
      { type: 'error' }
    )
    const res = await permanentDeleteDocument(row.id)
    if (res.code === 0) {
      ElMessage.success('永久删除成功')
      fetchList()
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const handleEmpty = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清空回收站吗？所有文档将被永久删除，此操作不可恢复！',
      '确认清空',
      { type: 'error' }
    )
    for (const item of tableData.value) {
      try {
        await permanentDeleteDocument(item.id)
      } catch (e) {
        console.error(e)
      }
    }
    ElMessage.success('回收站已清空')
    fetchList()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error('清空失败')
  }
}

onMounted(() => {
  fetchList()
})
</script>

<style lang="scss" scoped>
.document-trash {
  padding: 20px;
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .pagination-wrapper {
    display: flex;
    justify-content: flex-end;
    margin-top: 16px;
  }
}
</style>
