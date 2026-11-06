<template>
  <div class="skill-list">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>技能管理</span>
          <div class="button-group">
            <el-button type="default" @click="goToCategory">
              <el-icon><Folder /></el-icon>
              技能分类管理
            </el-button>
            <el-button type="primary" @click="handleAdd">
              <el-icon><Plus /></el-icon>
              新增技能
            </el-button>
          </div>
        </div>
      </template>

      <el-form :inline="true" :model="searchForm" class="mb-4">
        <el-form-item label="技能名称">
          <el-input v-model="searchForm.name" placeholder="请输入技能名称" clearable />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="searchForm.category_id" placeholder="请选择分类" clearable>
            <el-option v-for="cat in categories" :key="cat.id" :label="cat.name" :value="cat.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.status" placeholder="请选择状态" clearable>
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="resetSearch">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>

      <el-table :data="skills" style="width: 100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="技能名称" min-width="120" />
        <el-table-column prop="category_name" label="分类" width="120">
          <template #default="{ row }">
            <span v-if="row.category_name">{{ row.category_name }}</span>
            <span v-else class="text-gray">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="bound_tools" label="绑定的工具" width="180">
          <template #default="{ row }">
            <div v-if="row.bound_tools && row.bound_tools.length > 0" class="tool-tags">
              <el-tag v-for="tool in row.bound_tools" :key="tool" size="small" type="info" class="tool-tag">
                {{ tool }}
              </el-tag>
            </div>
            <span v-else class="text-gray">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="150" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'danger'">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" size="small" @click="handleEdit(row)">
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              <el-button type="info" size="small" @click="handleView(row)">
                <el-icon><Document /></el-icon>
                查看内容
              </el-button>
              <el-button type="danger" size="small" @click="handleDelete(row.id)">
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="mt-4">
        <el-pagination
          v-model:current-page="pageInfo.currentPage"
          v-model:page-size="pageInfo.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="pageInfo.total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="viewDialogVisible" title="技能内容" width="800px">
      <div class="skill-content">
        <div class="content-header">
          <h3>{{ currentSkill?.name }}</h3>
          <div v-if="currentSkill?.bound_tools && currentSkill.bound_tools.length > 0" class="bound-tools">
            <span class="bound-tools-label">绑定的工具：</span>
            <el-tag v-for="tool in currentSkill.bound_tools" :key="tool" size="small" type="info">
              {{ tool }}
            </el-tag>
          </div>
        </div>
        <div class="content-body">
          <div v-if="skillContent" class="markdown-content">
            <div v-html="renderMarkdown(skillContent)" />
          </div>
          <div v-else class="empty-content">
            暂无内容
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="formDialogVisible"
      :title="isEdit ? '编辑技能' : '创建技能'"
      width="900px"
      @close="resetForm"
    >
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="120px">
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
        <el-form-item label="绑定工具标签">
          <el-select
            v-model="formData.tool_tag_ids"
            multiple
            placeholder="请选择要绑定的工具标签"
            style="width: 100%"
          >
            <el-option
              v-for="tag in toolTags"
              :key="tag.id"
              :label="tag.name"
              :value="tag.id"
            />
          </el-select>
          <div class="form-hint">
            绑定工具标签后，技能将间接拥有该标签下的所有工具
          </div>
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
                placeholder="请输入技能内容（Markdown格式）"
              />
              <div v-else class="preview-content">
                <div v-if="formData.implementation" v-html="renderMarkdown(formData.implementation)" />
                <div v-else class="empty-preview">点击编辑模式输入内容</div>
              </div>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="formDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="saving">
            {{ isEdit ? '保存' : '创建' }}
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
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Search, Refresh, Edit, Delete, Document, Folder, Check } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getSkills,
  deleteSkill,
  getSkillContent,
  getActiveSkillCategories,
  getSkill,
  createSkill,
  updateSkill,
  getToolTagsWithCount
} from '@/api/agent'

const router = useRouter()
const loading = ref(false)
const skills = ref([])
const categories = ref([])
const toolTags = ref([])

const searchForm = reactive({
  name: '',
  category_id: null,
  status: ''
})

const pageInfo = reactive({
  currentPage: 1,
  pageSize: 10,
  total: 0
})

const viewDialogVisible = ref(false)
const currentSkill = ref(null)
const skillContent = ref('')

const formDialogVisible = ref(false)
const formRef = ref(null)
const saving = ref(false)
const editorMode = ref('markdown')
const currentSkillId = ref(null)

const isEdit = computed(() => !!currentSkillId.value)

const formData = reactive({
  name: '',
  description: '',
  status: 'active',
  category_id: null,
  tool_tag_ids: [],
  implementation: ''
})

const rules = {
  name: [{ required: true, message: '请输入技能名称', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const renderMarkdown = (content) => {
  if (!content) return ''
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

const fetchSkills = async () => {
  loading.value = true
  try {
    const res = await getSkills({
      skip: (pageInfo.currentPage - 1) * pageInfo.pageSize,
      limit: pageInfo.pageSize,
      ...searchForm
    })
    if (res.data) {
      skills.value = res.data.items || res.data
      pageInfo.total = res.data.total || skills.value.length
    }
  } catch (error) {
    ElMessage.error('获取技能列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pageInfo.currentPage = 1
  fetchSkills()
}

const resetSearch = () => {
  searchForm.name = ''
  searchForm.category_id = null
  searchForm.status = ''
  handleSearch()
}

const handleSizeChange = (size) => {
  pageInfo.pageSize = size
  fetchSkills()
}

const handleCurrentChange = (current) => {
  pageInfo.currentPage = current
  fetchSkills()
}

const handleAdd = () => {
  currentSkillId.value = null
  resetForm()
  formDialogVisible.value = true
}

const resetForm = () => {
  formData.name = ''
  formData.description = ''
  formData.status = 'active'
  formData.category_id = null
  formData.tool_tag_ids = []
  formData.implementation = ''
  editorMode.value = 'markdown'
  if (formRef.value) {
    formRef.value.clearValidate()
  }
}

const handleEdit = async (row) => {
  currentSkillId.value = row.id
  try {
    const res = await getSkill(row.id)
    if (res.data) {
      Object.assign(formData, res.data)
      if (!formData.tool_tag_ids) {
        formData.tool_tag_ids = []
      }
    }
    formDialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取技能信息失败')
    console.error(error)
  }
}

const handleView = async (row) => {
  currentSkill.value = row
  try {
    const res = await getSkillContent(row.id)
    skillContent.value = res.data.content || ''
  } catch (error) {
    skillContent.value = ''
    console.error(error)
  }
  viewDialogVisible.value = true
}

const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该技能吗？', '提示', { type: 'warning' })
    await deleteSkill(id)
    ElMessage.success('删除成功')
    fetchSkills()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (valid) {
      saving.value = true
      try {
        if (isEdit.value) {
          await updateSkill(currentSkillId.value, formData)
          ElMessage.success('更新成功')
        } else {
          await createSkill(formData)
          ElMessage.success('创建成功')
        }
        formDialogVisible.value = false
        fetchSkills()
      } catch (error) {
        ElMessage.error('保存失败')
        console.error(error)
      } finally {
        saving.value = false
      }
    }
  })
}

const publishSkill = async () => {
  saving.value = true
  try {
    await updateSkill(currentSkillId.value, {
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

const fetchToolTags = async () => {
  try {
    const res = await getToolTagsWithCount()
    if (res.data) {
      toolTags.value = res.data
    }
  } catch (error) {
    console.error('获取工具标签列表失败', error)
  }
}

const goToCategory = () => {
  router.push('/panel/agent/skills/category')
}

onMounted(() => {
  fetchCategories()
  fetchToolTags()
  fetchSkills()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.button-group {
  display: flex;
  gap: 8px;
}
.text-gray {
  color: #999;
}
.mb-4 {
  margin-bottom: 16px;
}
.mt-4 {
  margin-top: 16px;
}
.action-buttons {
  display: flex;
  justify-content: flex-start;
  align-items: center;
  gap: 4px;
}
.tool-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.tool-tag {
  margin: 2px 0;
}
.form-hint {
  font-size: 12px;
  color: #999;
  margin-top: 8px;
}
.skill-content {
  max-height: 500px;
  overflow-y: auto;
}
.content-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #eee;
}
.content-header h3 {
  margin: 0;
  font-size: 18px;
}
.bound-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.bound-tools-label {
  font-size: 12px;
  color: #666;
}
.content-body {
  padding: 8px;
}
.markdown-content {
  line-height: 1.8;
  color: #333;
}
.markdown-content h1 {
  font-size: 20px;
  margin: 16px 0 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #409eff;
}
.markdown-content h2 {
  font-size: 18px;
  margin: 14px 0 10px;
  color: #409eff;
}
.markdown-content h3 {
  font-size: 16px;
  margin: 12px 0 8px;
}
.markdown-content strong {
  font-weight: bold;
  color: #333;
}
.markdown-content em {
  font-style: italic;
  color: #666;
}
.markdown-content ul, .markdown-content ol {
  padding-left: 24px;
}
.markdown-content li {
  margin: 6px 0;
}
.empty-content {
  text-align: center;
  color: #999;
  padding: 40px;
}
.skill-content-editor {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  width: 100%;
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
.dialog-footer {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>


