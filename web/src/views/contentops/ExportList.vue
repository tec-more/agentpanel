<template>
  <div class="contentops-exports">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>成品导出</span>
          <el-button type="primary" :icon="Plus" @click="handleCreate">新建导出</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="list" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="content_id" label="内容ID" width="100" align="center" />
        <el-table-column label="导出平台" min-width="220">
          <template #default="{ row }">
            <el-tag v-for="p in (row.platforms || [])" :key="p" size="small" class="mr-1">
              {{ platformLabel(p) }}
            </el-tag>
            <span v-if="!row.platforms || !row.platforms.length">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="rule_version" label="规则版本" width="140" />
        <el-table-column prop="creator_id" label="导出人" width="100" align="center" />
        <el-table-column prop="created_at" label="导出时间" width="170" />
        <el-table-column label="操作" width="140" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Download" :loading="downloadingId === row.id"
                       @click="handleDownload(row)">下载 ZIP</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建导出弹窗 -->
    <el-dialog v-model="dialogVisible" title="新建导出" width="760px" destroy-on-close>
      <el-form label-width="100px">
        <el-form-item label="源内容">
          <el-select v-model="selectedContentId" placeholder="请选择内容" filterable style="width: 100%"
                     @change="onContentChange">
            <el-option v-for="c in contents" :key="c.id" :label="`#${c.id} ${c.title}`" :value="c.id" />
          </el-select>
        </el-form-item>
      </el-form>

      <el-divider content-position="left">选择各平台成品版本（仅已确认可导出）</el-divider>
      <el-table v-if="versions.length" :data="versions" border size="small">
        <el-table-column label="平台" width="140">
          <template #default="{ row }">{{ platformLabel(row.platform) }}</template>
        </el-table-column>
        <el-table-column label="版本ID" width="90" align="center" prop="id" />
        <el-table-column label="标题" min-width="180">
          <template #default="{ row }">{{ row.payload?.title || '-' }}</template>
        </el-table-column>
        <el-table-column label="确认状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.confirmed ? 'success' : 'warning'" size="small">
              {{ row.confirmed ? '已确认' : '未确认' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="导出" width="80" align="center">
          <template #default="{ row }">
            <el-checkbox v-model="selectedVersions[row.platform]" :disabled="!row.confirmed" />
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-else-if="selectedContentId" description="该内容暂无成品版本，请先在内容中心生成" />
      <el-empty v-else description="请先选择源内容" />

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitExport">打包导出</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Download } from '@element-plus/icons-vue'
import {
  getExportList, createExport, downloadExport, getContentList, getContentDetail, PLATFORMS
} from '@/api/contentops'

const loading = ref(false)
const list = ref([])
const dialogVisible = ref(false)
const submitting = ref(false)
const downloadingId = ref(null)

const contents = ref([])
const selectedContentId = ref(null)
const versions = ref([])
const selectedVersions = reactive({})

function platformLabel(v) {
  return PLATFORMS.find((p) => p.value === v)?.label || v
}

async function fetchList() {
  loading.value = true
  try {
    const { data } = await getExportList()
    list.value = data.items || []
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  dialogVisible.value = true
  selectedContentId.value = null
  versions.value = []
  Object.keys(selectedVersions).forEach((k) => delete selectedVersions[k])
  const { data } = await getContentList({ page: 1, page_size: 100 })
  contents.value = data.items || []
}

async function onContentChange(id) {
  if (!id) { versions.value = []; return }
  const { data } = await getContentDetail(id)
  versions.value = data.versions || []
  Object.keys(selectedVersions).forEach((k) => delete selectedVersions[k])
  // 默认勾选每个平台的首个已确认版本
  for (const v of versions.value) {
    if (v.confirmed && selectedVersions[v.platform] === undefined) {
      selectedVersions[v.platform] = v.id
    }
  }
}

async function submitExport() {
  const mapping = {}
  for (const [platform, vid] of Object.entries(selectedVersions)) {
    if (vid) mapping[platform] = vid
  }
  if (!selectedContentId.value || !Object.keys(mapping).length) {
    ElMessage.warning('请选择内容和至少一个已确认的成品版本')
    return
  }
  submitting.value = true
  try {
    await createExport({ content_id: selectedContentId.value, platform_version_ids: mapping })
    ElMessage.success('导出完成，已生成台账记录')
    dialogVisible.value = false
    fetchList()
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    submitting.value = false
  }
}

async function handleDownload(row) {
  downloadingId.value = row.id
  try {
    const resp = await downloadExport(row.id)
    const blob = resp instanceof Blob ? resp : resp.data
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `contentops_export_${row.id}.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error(e.message || '下载失败')
  } finally {
    downloadingId.value = null
  }
}

onMounted(fetchList)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.mr-1 { margin-right: 4px; }
</style>
