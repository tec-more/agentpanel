<template>
  <div class="usage-records">
    <!-- 统一使用记录管理 -->
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>大模型使用记录管理</span>
        </div>
      </template>

      <!-- 搜索栏 -->
      <el-form :inline="true" :model="searchForm" class="search-form mb-4">
        <el-form-item label="客户ID">
          <el-input v-model="searchForm.customer_id" placeholder="请输入客户ID" clearable style="width: 150px" />
        </el-form-item>
        <el-form-item label="模型ID">
          <el-input v-model="searchForm.model_id" placeholder="请输入模型ID" clearable style="width: 150px" />
        </el-form-item>
        <el-form-item label="记录类型">
          <el-select v-model="searchForm.record_type" placeholder="请选择" clearable style="width: 150px">
            <el-option label="语音识别/同声传译" value="voice" />
            <el-option label="语音合成" value="tts" />
            <el-option label="声音复刻" value="voice_clone" />
            <el-option label="文本对话" value="conversation" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择" clearable style="width: 120px">
            <el-option label="处理中" value="processing" />
            <el-option label="完成" value="completed" />
            <el-option label="失败" value="failed" />
            <el-option label="活跃" value="active" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="fetchUsageRecords">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <el-table v-loading="loading" :data="recordsList" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="record_id" label="记录ID" min-width="150" show-overflow-tooltip />
        <el-table-column prop="customer_id" label="客户ID" width="100" align="center" />
        <el-table-column prop="model_id" label="模型ID" width="100" align="center" />
        <el-table-column prop="record_type" label="记录类型" width="150" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.record_type === 'voice'" type="primary">语音识别/同声传译</el-tag>
            <el-tag v-else-if="row.record_type === 'tts'" type="success">语音合成</el-tag>
            <el-tag v-else-if="row.record_type === 'voice_clone'" type="info">声音复刻</el-tag>
            <el-tag v-else-if="row.record_type === 'conversation'" type="warning">文本对话</el-tag>
            <span v-else>{{ row.record_type }}</span>
          </template>
        </el-table-column>
        <el-table-column label="内容" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">
            <div v-if="row.input_text">{{ row.input_text.length > 50 ? row.input_text.substring(0, 50) + '...' : row.input_text }}</div>
            <div v-else-if="row.audio_file">{{ row.audio_file }}</div>
            <div v-else-if="row.voice_name">声音复刻: {{ row.voice_name }}</div>
            <div v-else>-</div>
          </template>
        </el-table-column>
        <el-table-column label="语言" width="180" align="center">
          <template #default="{ row }">
            <div v-if="row.source_language">{{ row.source_language }} → {{ row.target_language || '-' }}</div>
            <div v-else>-</div>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'processing'" type="info">处理中</el-tag>
            <el-tag v-else-if="row.status === 'completed'" type="success">完成</el-tag>
            <el-tag v-else-if="row.status === 'failed'" type="danger">失败</el-tag>
            <el-tag v-else-if="row.status === 'active'" type="warning">活跃</el-tag>
            <span v-else>{{ row.status }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="200" align="center">
          <template #default="{ row }">
            <div v-if="row.start_time">{{ formatDateTime(row.start_time) }}</div>
            <div v-else>{{ formatDateTime(row.created_at) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="时长" width="100" align="center">
          <template #default="{ row }">
            <div v-if="row.start_time && row.end_time">{{ calculateDuration(row.start_time, row.end_time) }}</div>
            <div v-else>-</div>
          </template>
        </el-table-column>
        <el-table-column label="费用" width="100" align="center">
          <template #default="{ row }">
            <div>¥{{ (row.cost || 0).toFixed(4) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleViewDetail(row)">查看</el-button>
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
          @size-change="fetchUsageRecords"
          @current-change="fetchUsageRecords"
        />
      </div>
    </el-card>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailDialogVisible" title="记录详情" width="800px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="记录ID">{{ detailRecord.record_id }}</el-descriptions-item>
        <el-descriptions-item label="客户ID">{{ detailRecord.customer_id }}</el-descriptions-item>
        <el-descriptions-item label="模型ID">{{ detailRecord.model_id }}</el-descriptions-item>
        <el-descriptions-item label="记录类型">
          <el-tag v-if="detailRecord.record_type === 'voice'" type="primary">语音识别/同声传译</el-tag>
          <el-tag v-else-if="detailRecord.record_type === 'tts'" type="success">语音合成</el-tag>
          <el-tag v-else-if="detailRecord.record_type === 'voice_clone'" type="info">声音复刻</el-tag>
          <el-tag v-else-if="detailRecord.record_type === 'conversation'" type="warning">文本对话</el-tag>
          <span v-else>{{ detailRecord.record_type }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="音频文件" v-if="detailRecord.audio_file">{{ detailRecord.audio_file }}</el-descriptions-item>
        <el-descriptions-item label="音频格式" v-if="detailRecord.audio_format">{{ detailRecord.audio_format }}</el-descriptions-item>
        <el-descriptions-item label="源语言" v-if="detailRecord.source_language">{{ detailRecord.source_language }}</el-descriptions-item>
        <el-descriptions-item label="目标语言" v-if="detailRecord.target_language">{{ detailRecord.target_language }}</el-descriptions-item>
        <el-descriptions-item label="音色" v-if="detailRecord.voice_type">{{ detailRecord.voice_type }}</el-descriptions-item>
        <el-descriptions-item label="复刻ID" v-if="detailRecord.clone_id">{{ detailRecord.clone_id }}</el-descriptions-item>
        <el-descriptions-item label="音色ID" v-if="detailRecord.voice_id">{{ detailRecord.voice_id }}</el-descriptions-item>
        <el-descriptions-item label="音色名称" v-if="detailRecord.voice_name">{{ detailRecord.voice_name }}</el-descriptions-item>
        <el-descriptions-item label="对话ID" v-if="detailRecord.conversation_id">{{ detailRecord.conversation_id }}</el-descriptions-item>
        <el-descriptions-item label="开始时间" :span="2">{{ detailRecord.start_time ? formatDateTime(detailRecord.start_time) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="结束时间" :span="2">{{ detailRecord.end_time ? formatDateTime(detailRecord.end_time) : '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态" :span="2">
          <el-tag v-if="detailRecord.status === 'processing'" type="info">处理中</el-tag>
          <el-tag v-else-if="detailRecord.status === 'completed'" type="success">完成</el-tag>
          <el-tag v-else-if="detailRecord.status === 'failed'" type="danger">失败</el-tag>
          <el-tag v-else-if="detailRecord.status === 'active'" type="warning">活跃</el-tag>
          <span v-else>{{ detailRecord.status }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="错误信息" :span="2">{{ detailRecord.error_message || '-' }}</el-descriptions-item>
        <el-descriptions-item label="输入文本" :span="2">
          <template v-if="detailRecord.input_text">
            <el-popover placement="top" :width="600" trigger="click">
              <template #reference>
                <span class="text-primary cursor-pointer">{{ detailRecord.input_text.length > 50 ? detailRecord.input_text.substring(0, 50) + '...' : detailRecord.input_text }}</span>
              </template>
              <div class="text-break popover-content">{{ detailRecord.input_text }}</div>
            </el-popover>
          </template>
          <template v-else>
            <span class="text-gray">-</span>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="输出文本" :span="2">
          <template v-if="detailRecord.output_text">
            <el-popover placement="top" :width="600" trigger="click">
              <template #reference>
                <span class="text-primary cursor-pointer">{{ detailRecord.output_text.length > 50 ? detailRecord.output_text.substring(0, 50) + '...' : detailRecord.output_text }}</span>
              </template>
              <div class="text-break popover-content">{{ detailRecord.output_text }}</div>
            </el-popover>
          </template>
          <template v-else>
            <span class="text-gray">-</span>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="Token统计" :span="2">
          <div>总计: {{ detailRecord.tokens || 0 }}</div>
        </el-descriptions-item>
        <el-descriptions-item label="费用" :span="2">¥{{ (detailRecord.cost || 0).toFixed(4) }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Search, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getUnifiedUsageRecords } from '@/api/llm'

const loading = ref(false)
const recordsList = ref([])
const detailDialogVisible = ref(false)
const detailRecord = ref({})

const searchForm = reactive({
  customer_id: null,
  model_id: null,
  record_type: null,
  status: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

// 获取统一使用记录列表
const fetchUsageRecords = async () => {
  loading.value = true
  try {
    const { data } = await getUnifiedUsageRecords({
      ...searchForm,
      page: pagination.page,
      page_size: pagination.pageSize
    })
    recordsList.value = data.items || []
    pagination.total = data.total || 0
  } catch (error) {
    ElMessage.error('获取使用记录失败')
  } finally {
    loading.value = false
  }
}

// 查看详情
const handleViewDetail = (row) => {
  detailRecord.value = { ...row }
  detailDialogVisible.value = true
}

// 重置
const handleReset = () => {
  searchForm.customer_id = null
  searchForm.model_id = null
  searchForm.record_type = null
  searchForm.status = null
  pagination.page = 1
  fetchUsageRecords()
}

// 格式化日期时间
const formatDateTime = (dateTime) => {
  if (!dateTime) return ''
  const date = new Date(dateTime)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 计算时长
const calculateDuration = (startTime, endTime) => {
  if (!startTime || !endTime) return ''
  const start = new Date(startTime)
  const end = new Date(endTime)
  const duration = (end - start) / 1000 // 秒
  if (duration < 60) {
    return `${duration.toFixed(1)}秒`
  } else {
    const minutes = Math.floor(duration / 60)
    const seconds = Math.floor(duration % 60)
    return `${minutes}分${seconds}秒`
  }
}

onMounted(() => {
  fetchUsageRecords()
})
</script>

<style scoped>
.usage-records {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 16px;
}

.pagination-wrapper {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.text-primary {
  color: #409eff;
}

.text-gray {
  color: #909399;
}

.cursor-pointer {
  cursor: pointer;
}

.text-break {
  word-break: break-all;
}

.popover-content {
  max-height: 300px;
  overflow-y: auto;
  padding: 10px;
  line-height: 1.5;
}

.mb-4 {
  margin-bottom: 16px;
}
</style>


