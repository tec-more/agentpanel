<template>
  <div class="rich-text-editor">
    <div ref="toolbarRef" class="editor-toolbar" />
    <div ref="editorRef" class="editor-body" />
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, shallowRef, watch } from 'vue'
import { createEditor, createToolbar } from '@wangeditor/editor'
import '@wangeditor/editor/dist/css/style.css'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '请输入正文…' }
})
const emit = defineEmits(['update:modelValue'])

const toolbarRef = ref(null)
const editorRef = ref(null)
const editor = shallowRef(null)
const toolbar = shallowRef(null)
let syncing = false

onMounted(() => {
  editor.value = createEditor({
    selector: editorRef.value,
    html: props.modelValue || '',
    config: {
      placeholder: props.placeholder,
      onValueChanged: () => {
        if (syncing || !editor.value) return
        emit('update:modelValue', editor.value.getHtml())
      }
    }
  })
  toolbar.value = createToolbar({
    editor: editor.value,
    selector: toolbarRef.value,
    config: {}
  })
})

watch(() => props.modelValue, (val) => {
  if (!editor.value || syncing) return
  if (val !== editor.value.getHtml()) {
    syncing = true
    editor.value.setHtml(val || '')
    syncing = false
  }
})

onBeforeUnmount(() => {
  if (toolbar.value) toolbar.value.destroy()
  if (editor.value) editor.value.destroy()
})
</script>

<style scoped>
.editor-toolbar { border: 1px solid #dcdfe6; border-bottom: none; background: #fff; }
.editor-body { border: 1px solid #dcdfe6; min-height: 240px; }
</style>
