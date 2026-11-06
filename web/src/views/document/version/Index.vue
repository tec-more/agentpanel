<template>
  <div class="document-version">
    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <el-button :icon="ArrowLeft" @click="goBack">返回</el-button>
            <span class="doc-title">{{ document?.title }} - 版本历史</span>
          </div>
          <el-button type="primary" :icon="Upload" @click="showUploadDialog = true">
            上传新版本
          </el-button>
        </div>
      </template>

      <el-timeline v-if="versionList.length > 0" class="version-timeline">
        <el-timeline-item
          v-for="(ver, index) in versionList"
          :key="ver.id"
          :timestamp="formatDate(ver.created_at)"
          :color="index === 0 ? '#409EFF' : '#909399'"
          :hollow="index !== 0"
        >
          <div class="version-item">
            <div class="version-header">
              <el-tag :type="index === 0 ? 'primary' : 'info'" size="large">
                v{{ ver.version }}
              </el-tag>
              <el-tag v-if="index === 0" type="success" size="small" style="margin-left: 8px;">
                当前版本
              </el-tag>
              <span class="version-file">{{ ver.file_path?.split('\\').pop()?.split('/').pop() }}</span>
            </div>
            <div class="version-info">
              <span>文件大小: {{ formatFileSize(ver.file_size) }}</span>
              <span v-if="ver.change_log" class="change-log">变更说明: {{ ver.change_log }}</span>
            </div>
            <div class="version-actions">
              <el-button link type="primary" size="small" @click="handlePreview(ver)">
                预览
              </el-button>
              <el-button link type="success" size="small" @click="handleDownload(ver)">
                下载
              </el-button>
              <el-button
                v-if="index !== 0"
                link
                type="warning"
                size="small"
                @click="handleRollback(ver)"
              >
                回滚到此版本
              </el-button>
              <el-button
                v-if="index !== 0"
                link
                type="danger"
                size="small"
                @click="handleDelete(ver)"
              >
                删除
              </el-button>
            </div>
          </div>
        </el-timeline-item>
      </el-timeline>

      <el-empty v-else description="暂无版本记录">
        <el-button type="primary" :icon="Upload" @click="showUploadDialog = true">
          上传第一个版本
        </el-button>
      </el-empty>
    </el-card>

    <!-- 上传新版本对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传新版本" width="500px">
      <el-form :model="uploadForm" label-width="100px">
        <el-form-item label="当前版本">
          <el-tag>v{{ document?.version || 1 }}</el-tag>
          <span style="margin-left: 8px;">→</span>
          <el-tag type="primary" style="margin-left: 8px;">v{{ (document?.version || 0) + 1 }}</el-tag>
        </el-form-item>
        <el-form-item label="新文件">
          <el-upload
            v-model:file-list="uploadForm.fileList"
            :auto-upload="false"
            :on-change="handleFileChange"
            :limit="1"
          >
            <el-button type="primary" :icon="Upload">选择新文件</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item label="变更说明" required>
          <el-input
            v-model="uploadForm.change_log"
            type="textarea"
            :rows="3"
            placeholder="请描述此版本的变更内容"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button
          type="primary"
          @click="handleUploadNewVersion"
          :loading="uploading"
          :disabled="!uploadForm.file"
        >
          上传
        </el-button>
      </template>
    </el-dialog>

    <!-- 回滚对话框 -->
    <el-dialog v-model="showRollbackDialog" title="确认回滚" width="450px">
      <div v-if="rollingBackVer">
        <p>您将要将文档回滚到 <strong>v{{ rollingBackVer.version }}</strong></p>
        <p class="rollback-tip">
          回滚操作会创建一个新的版本 v{{ (document?.version || 0) + 1 }}，
          该版本的内容将与 v{{ rollingBackVer.version }} 相同。
        </p>
        <el-form :model="rollbackForm" label-width="80px" style="margin-top: 16px;">
          <el-form-item label="变更说明">
            <el-input
              v-model="rollbackForm.change_log"
              type="textarea"
              :rows="2"
              placeholder="可选：描述回滚原因"
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="showRollbackDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmRollback" :loading="rolling">
          确认回滚
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Upload } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getVersionList,
  getDocumentDetail,
  uploadDocumentNewVersion,
  deleteVersion,
  rollbackVersion
} from '@/api/document'
import request from '@/utils/request'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const uploading = ref(false)
const rolling = ref(false)
const document = ref(null)
const versionList = ref([])
const showUploadDialog = ref(false)
const showRollbackDialog = ref(false)
const rollingBackVer = ref(null)

const uploadForm = reactive({
  fileList: [],
  file: null,
  change_log: ''
})

const rollbackForm = reactive({
  change_log: ''
})

const docId = ref(parseInt(route.params.id) || parseInt(route.query.doc_id))

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const formatFileSize = (size) => {
  if (!size) return '-'
  if (size < 1024) return size + ' B'
  if (size < 1024 * 1024) return (size / 1024).toFixed(2) + ' KB'
  return (size / 1024 / 1024).toFixed(2) + ' MB'
}

const goBack = () => {
  router.back()
}

const fetchDocument = async () => {
  try {
    const res = await getDocumentDetail(docId.value)
    if (res.code === 0) {
      document.value = res.data
    }
  } catch (e) {
    console.error('获取文档详情失败:', e)
  }
}

const fetchVersions = async () => {
  loading.value = true
  try {
    const res = await getVersionList(docId.value, { page_size: 50 })
    if (res.code === 0) {
      versionList.value = res.data.items
    }
  } catch (e) {
    ElMessage.error('获取版本列表失败')
  } finally {
    loading.value = false
  }
}

const handleFileChange = (file) => {
  uploadForm.file = file.raw
}

const handleUploadNewVersion = async () => {
  if (!uploadForm.file) {
    ElMessage.warning('请先选择文件')
    return
  }
  if (!uploadForm.change_log.trim()) {
    ElMessage.warning('请填写变更说明')
    return
  }

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', uploadForm.file)
    formData.append('change_log', uploadForm.change_log)

    const res = await uploadDocumentNewVersion(docId.value, formData)
    if (res.code === 0) {
      ElMessage.success('新版本上传成功')
      showUploadDialog.value = false
      resetUploadForm()
      fetchDocument()
      fetchVersions()
    } else {
      ElMessage.error(res.msg || '上传失败')
    }
  } catch (e) {
    ElMessage.error('上传失败: ' + e.message)
  } finally {
    uploading.value = false
  }
}

const resetUploadForm = () => {
  uploadForm.fileList = []
  uploadForm.file = null
  uploadForm.change_log = ''
}

const handlePreview = async (ver) => {
  try {
    const res = await request.get(`/v1/document/preview/version/${ver.id}`, {
      responseType: 'blob'
    })
    if (res && res.data) {
      const blob = new Blob([res.data])
      const url = window.URL.createObjectURL(blob)
      window.open(url, '_blank')
    }
  } catch (e) {
    ElMessage.error('预览失败')
  }
}

const handleDownload = async (ver) => {
  try {
    const res = await request.get(`/v1/document/preview/version/${ver.id}/download`, {
      responseType: 'blob'
    })
    if (res && res.data) {
      const blob = new Blob([res.data])
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = document.value?.file_name || 'download'
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
      ElMessage.success('下载成功')
    }
  } catch (e) {
    const msg = e.response?.data?.msg || e.message || '下载失败'
    ElMessage.error(msg)
  }
}

const handleRollback = (ver) => {
  rollingBackVer.value = ver
  rollbackForm.change_log = `回滚到 v${ver.version}`
  showRollbackDialog.value = true
}

const confirmRollback = async () => {
  rolling.value = true
  try {
    const res = await rollbackVersion(docId.value, {
      version_id: rollingBackVer.value.id,
      change_log: rollbackForm.change_log
    })
    if (res.code === 0) {
      ElMessage.success('回滚成功')
      showRollbackDialog.value = false
      fetchDocument()
      fetchVersions()
    } else {
      ElMessage.error(res.msg || '回滚失败')
    }
  } catch (e) {
    ElMessage.error('回滚失败: ' + e.message)
  } finally {
    rolling.value = false
  }
}

const handleDelete = async (ver) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除版本 v${ver.version} 吗？此操作不可恢复。`,
      '确认删除',
      { type: 'warning' }
    )
    const res = await deleteVersion(ver.id)
    if (res.code === 0) {
      ElMessage.success('版本删除成功')
      fetchVersions()
    } else {
      ElMessage.error(res.msg || '删除失败')
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  fetchDocument()
  fetchVersions()
})
</script>

<style lang="scss" scoped>
.document-version {
  padding: 20px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;
      .doc-title {
        font-size: 16px;
        font-weight: 600;
      }
    }
  }
}

.version-timeline {
  padding: 0 20px;
}

.version-item {
  .version-header {
    display: flex;
    align-items: center;
    margin-bottom: 8px;

    .version-file {
      margin-left: 12px;
      color: var(--el-text-color-secondary);
    }
  }

  .version-info {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 12px;
    color: var(--el-text-color-secondary);
    font-size: 13px;

    .change-log {
      color: var(--el-text-color-primary);
    }
  }

  .version-actions {
    display: flex;
    gap: 16px;
  }
}

.rollback-tip {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
}
</style>
