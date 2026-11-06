<template>
  <el-select
    :model-value="modelValue"
    :multiple="multiple"
    filterable
    remote
    clearable
    :remote-method="onSearch"
    :loading="loading"
    :disabled="!subjectType"
    placeholder="输入名称/邮箱搜索主体"
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
import { getGrantSubjects } from '@/api/grant'

// FR-06：主体选择器（远程搜索；默认多选，multiple=false 时单选，供组织 owner/成员选择复用）
const props = defineProps({
  modelValue: {
    type: [Array, Number, String],
    default: () => []
  },
  subjectType: {
    type: String,
    default: ''
  },
  multiple: {
    type: Boolean,
    default: true
  }
})
const emit = defineEmits(['update:modelValue'])

const loading = ref(false)
const options = ref([])
// 缓存已加载过的主体（id -> item），避免搜索切换时已选项显示成裸 id
const itemCache = new Map()

// 已选值统一为数组（单选模式下兼容标量）
const selectedValues = () => {
  const value = props.modelValue
  if (props.multiple) return Array.isArray(value) ? value : []
  return value === '' || value === null || value === undefined ? [] : [value]
}

// 合并选项：搜索结果 + 已选中项（从缓存取 label）
const mergeOptions = (items) => {
  const merged = [...items]
  const ids = new Set(items.map((i) => i.value))
  for (const id of selectedValues()) {
    if (!ids.has(id) && itemCache.has(id)) {
      merged.unshift(itemCache.get(id))
    }
  }
  return merged
}

// 加载主体选项
const loadOptions = async (keyword = '') => {
  if (!props.subjectType) {
    options.value = []
    return
  }
  loading.value = true
  try {
    const res = await getGrantSubjects({ type: props.subjectType, keyword, page: 1, page_size: 20 })
    const d = res?.data ?? res
    const items = (d.items || []).map((item) => ({
      value: item.id,
      label: item.label,
      // §4.3/测试节点1 Q3 裁定：org 选项标注组织授权语义；其余类型显示邮箱
      note: item.extra?.email || (props.subjectType === 'org' ? '全体成员获得授权，成员变动自动生效' : '')
    }))
    items.forEach((item) => itemCache.set(item.value, item))
    options.value = mergeOptions(items)
  } catch (e) {
    // 错误已由拦截器提示
  } finally {
    loading.value = false
  }
}

const onSearch = (keyword) => {
  loadOptions(keyword)
}

// 切换主体类型：清空选项与已选值，重新加载首屏
watch(
  () => props.subjectType,
  () => {
    itemCache.clear()
    options.value = []
    emit('update:modelValue', props.multiple ? [] : '')
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
