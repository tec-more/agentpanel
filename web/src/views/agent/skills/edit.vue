<template>
  <div class="skill-edit">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ isEdit ? '编辑技能' : '创建技能' }}</span>
          <div class="header-right">
            <el-button type="primary" @click="handleSubmit" :loading="saving">
              <el-icon><Check /></el-icon>
              <span v-if="isEdit">保存</span>
              <span v-else>创建</span>
            </el-button>
            <el-button 
              type="warning" 
              @click="publishSkill" 
              v-if="isEdit && formData.status !== 'active'"
            >
              <el-icon><Check /></el-icon>
              发布
            </el-button>
          </div>
        </div>
      </template>

      <el-form :model="formData" :rules="rules" ref="formRef" label-width="120px" style="max-width: 900px;">
        <el-form-item label="技能名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入技能名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="formData.description" type="textarea" :rows="2" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="formData.status" placeholder="请选择状态" style="width: 100%">
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="formData.category_id" placeholder="请选择分类" style="width: 100%" clearable>
            <el-option v-for="cat in categories" :key="cat.id" :label="cat.name" :value="cat.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="技能内容">
          <div class="skill-content-editor">
            <div class="editor-tabs">
              <el-button 
                :type="editorMode === 'markdown' ? 'primary' : ''" 
                @click="editorMode = 'markdown'"
                size="small"
              >
                Markdown 编辑
              </el-button>
              <el-button 
                :type="editorMode === 'preview' ? 'primary' : ''" 
                @click="editorMode = 'preview'"
                size="small"
              >
                预览
              </el-button>
            </div>
            <div class="editor-content">
              <el-input 
                v-if="editorMode === 'markdown'"
                v-model="formData.implementation" 
                type="textarea" 
                :rows="15" 
                placeholder="请输入技能内容（Markdown格式）

# 技能名称

## 🎯 约束条件
- 约束1
- 约束2

## 📝 规范流程
步骤1 → 步骤2 → 步骤3

## 💬 示例对话
用户：...
助手：..."
              />
              <div v-else class="preview-content">
                <div v-if="formData.implementation" v-html="renderMarkdown(formData.implementation)" />
                <div v-else class="empty-preview">点击编辑模式输入内容</div>
              </div>
            </div>
          </div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Check } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getSkill, createSkill, updateSkill, getActiveSkillCategories } from '@/api/agent'

const route = useRoute()
const router = useRouter()
const formRef = ref(null)
const saving = ref(false)
const editorMode = ref('markdown')
const categories = ref([])

const skillId = route.params.id
const isEdit = computed(() => !!skillId)

const formData = reactive({
  name: '',
  description: '',
  status: 'active',
  category_id: null,
  implementation: ''
})

const rules = {
  name: [{ required: true, message: '请输入技能名称', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

const goBack = () => {
  router.push('/panel/agent/skills')
}

const renderMarkdown = (content) => {
  return content
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*)\*/gim, '<em>$1</em>')
    .replace(/^- (.*$)/gim, '<li>$1</li>')
    .replace(/^(\d+)\. (.*$)/gim, '<li>$1. $2</li>')
    .replace(/\n/gim, '<br/>')
}

const fetchSkill = async () => {
  if (!skillId) return
  try {
    const res = await getSkill(skillId)
    Object.assign(formData, res.data)
  } catch (error) {
    ElMessage.error('获取技能信息失败')
    console.error(error)
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      saving.value = true
      try {
        if (isEdit.value) {
          await updateSkill(skillId, formData)
          ElMessage.success('更新成功')
        } else {
          console.log('Creating skill with data:', formData)
          const res = await createSkill(formData)
          console.log('createSkill response:', res)
          ElMessage.success('创建成功')
          const editUrl = `/panel/agent/skills/edit/${res.data.id}`
          console.log('Redirecting to:', editUrl)
          router.push(editUrl)
        }
      } catch (error) {
        ElMessage.error('保存失败')
        console.error('Error saving skill:', error)
      } finally {
        saving.value = false
      }
    }
  })
}

const publishSkill = async () => {
  saving.value = true
  try {
    await updateSkill(skillId, {
      ...formData,
      status: 'active'
    })
    formData.status = 'active'
    ElMessage.success('发布成功')
  } catch (error) {
    ElMessage.error('发布失败')
    console.error(error)
  } finally {
    saving.value = false
  }
}

const fetchCategories = async () => {
  try {
    const res = await getActiveSkillCategories()
    if (res.data) {
      categories.value = res.data
    }
  } catch (error) {
    console.error('获取分类列表失败', error)
  }
}

onMounted(() => {
  fetchCategories()
  if (isEdit.value) {
    fetchSkill()
  }
})
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  gap: 16px;
}
.header-right {
  margin-left: auto;
  display: flex;
  gap: 10px;
}
.skill-content-editor {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  width:100%;
  overflow: hidden;
}
.editor-tabs {
  display: flex;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
  padding: 4px;
  gap: 4px;
}
.editor-content {
  padding: 8px;
}
.editor-content textarea {
  width: 100%;
  min-height: 300px;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', monospace;
  font-size: 14px;
  line-height: 1.6;
}
.preview-content {
  min-height: 300px;
  line-height: 1.8;
  color: #333;
  padding: 8px;
}
.preview-content h1 {
  font-size: 20px;
  margin: 16px 0 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #409eff;
}
.preview-content h2 {
  font-size: 18px;
  margin: 14px 0 10px;
  color: #409eff;
}
.preview-content h3 {
  font-size: 16px;
  margin: 12px 0 8px;
}
.preview-content strong {
  font-weight: bold;
  color: #333;
}
.preview-content em {
  font-style: italic;
  color: #666;
}
.preview-content ul, .preview-content ol {
  padding-left: 24px;
}
.preview-content li {
  margin: 6px 0;
}
.empty-preview {
  text-align: center;
  color: #999;
  padding: 40px;
}
</style>


