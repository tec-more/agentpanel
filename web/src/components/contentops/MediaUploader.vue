<template>
  <div class="media-uploader">
    <el-upload
      :action="uploadUrl"
      :headers="uploadHeaders"
      :data="uploadData"
      :accept="accept"
      :show-file-list="false"
      :before-upload="beforeUpload"
      :on-success="handleSuccess"
      :on-error="handleError"
    >
      <el-button :loading="uploading" :icon="UploadFilled">
        {{ uploading ? '上传中…' : buttonText }}
      </el-button>
    </el-upload>
    <div class="media-list">
      <div v-for="a in modelValue" :key="a.id" class="media-item">
        <el-image v-if="a.content_type?.startsWith('image')" :src="a.url" fit="cover"
                  class="media-thumb" :preview-src-list="[a.url]" />
        <div v-else class="media-video-icon">视频</div>
        <div class="media-meta">
          <span class="media-name">{{ a.extra?.original_name || a.kind }}</span>
          <span class="media-size">{{ formatSize(a.size_bytes) }}</span>
        </div>
        <el-button type="danger" link :icon="Delete" @click="handleRemove(a)" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Delete } from '@element-plus/icons-vue'
import { API_BASE } from '@/utils/apiBase'
import { deleteMedia } from '@/api/contentops'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },  // asset dict 列表
  kind: { type: String, default: 'image' },        // image / cover / video
  contentId: { type: Number, default: null },
  limit: { type: Number, default: 9 },
  buttonText: { type: String, default: '上传素材' }
})
const emit = defineEmits(['update:modelValue'])

const uploading = ref(false)
const uploadUrl = computed(() => `${API_BASE}/v1/contentops/media/upload`)
const uploadHeaders = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('token') || ''}` }))
const uploadData = computed(() => ({
  kind: props.kind,
  ...(props.contentId ? { content_id: props.contentId } : {})
}))
const accept = computed(() => props.kind === 'video' ? '.mp4,.mov,.avi,.webm,.mkv' : '.jpg,.jpeg,.png,.gif,.webp')

function beforeUpload(file) {
  uploading.value = true
  const max = props.kind === 'video' ? 2 * 1024 : 20
  if (file.size / 1024 / 1024 > max) {
    ElMessage.error(`文件不能超过 ${max}MB`)
    uploading.value = false
    return false
  }
  return true
}
function handleSuccess(resp) {
  uploading.value = false
  if (resp.code !== 0 && resp.code !== 200) {
    ElMessage.error(resp.msg || '上传失败')
    return
  }
  if (props.modelValue.length >= props.limit) {
    ElMessage.warning(`最多上传 ${props.limit} 个`)
    return
  }
  emit('update:modelValue', [...props.modelValue, resp.data])
  ElMessage.success('上传成功')
}
function handleError() {
  uploading.value = false
  ElMessage.error('上传失败')
}
async function handleRemove(a) {
  await ElMessageBox.confirm('确认删除该素材？', '提示', { type: 'warning' })
  if (a.id) {
    try { await deleteMedia(a.id) } catch (_) {}
  }
  emit('update:modelValue', props.modelValue.filter(x => x.id !== a.id))
}
function formatSize(b) {
  if (!b) return '-'
  return b > 1024 * 1024 ? `${(b / 1024 / 1024).toFixed(1)}MB` : `${(b / 1024).toFixed(0)}KB`
}
</script>

<style scoped>
.media-list { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.media-item { display: flex; align-items: center; gap: 6px; border: 1px solid #e4e7ed; border-radius: 4px; padding: 4px; }
.media-thumb { width: 56px; height: 56px; border-radius: 3px; }
.media-video-icon { width: 56px; height: 56px; display: flex; align-items: center; justify-content: center; background: #f0f2f5; font-size: 12px; color: #909399; }
.media-meta { display: flex; flex-direction: column; font-size: 12px; max-width: 130px; }
.media-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.media-size { color: #909399; }
</style>
