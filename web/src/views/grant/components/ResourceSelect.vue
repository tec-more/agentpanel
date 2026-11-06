<template>
  <el-select
    :model-value="modelValue"
    filterable
    remote
    clearable
    :remote-method="onSearch"
    :loading="loading"
    :disabled="!resourceType"
    placeholder="输入名称搜索资源"
    style="width: 100%"
    @update:model-value="(val) => emit('update:modelValue', val)"
  >
    <el-option v-for="item in options" :key="item.value" :label="item.label" :value="item.value">
      <span>{{ item.label }}</span>
      <span v-if="item.note" class="option-note">{{ item.note }}</span>
    </el-option>
  </el-select>
</template>

<script setup>
import { ref, watch } from 'vue'
import { getResourceOptions } from '@/api/grant'

// FR-05：资源单选选择器（远程搜索）
const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  resourceType: {
    type: String,
    default: ''
  }
})
const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const options = ref([])

// 加载资源选项
const loadOptions = async (keyword = '') => {
  if (!props.resourceType) {
    options.value = []
    return
  }
  loading.value = true
  try {
    const res = await getResourceOptions({ type: props.resourceType, keyword })
    const d = res?.data ?? res
    options.value = (d.items || []).map((item) => {
      // node_type 附注 code；其余资源附注 provider/status
      let note = ''
      if (props.resourceType === 'node_type' && item.extra?.code) {
        note = item.extra.code
      } else if (item.extra?.provider) {
        note = item.extra.provider
      } else if (item.extra?.status) {
        note = item.extra.status
      }
      return { value: String(item.id), label: item.label, note }
    })
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    loading.value = false
  }
}

const onSearch = (keyword) => {
  loadOptions(keyword)
}

// 切换资源类型：清空选项并重新加载首屏
watch(
  () => props.resourceType,
  () => {
    options.value = []
    loadOptions('')
  },
  { immediate: true }
)
</script>

<style scoped>
.option-note {
  float: right;
  color: #909399;
  font-size: 12px;
}
</style>
