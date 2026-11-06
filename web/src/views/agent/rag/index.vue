<template>
  <div class="rag-container">
    <el-card class="mb-4">
      <template #header>
        <div class="card-header">
          <span>RAG知识库</span>
          <el-button type="primary" @click="handleAddKB">
            <el-icon><Plus /></el-icon>
            新增知识库
          </el-button>
        </div>
      </template>

      <el-table :data="knowledgeBases" style="width: 100%" v-loading="kbLoading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="知识库名称" min-width="150" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'danger'">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="vector_dimension" label="向量维度" width="100" />
        <el-table-column prop="document_count" label="文档数量" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="250" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" size="small" @click="handleSelectKB(row)">
                管理文档
              </el-button>
              <el-button type="info" size="small" @click="handleEditKB(row)">
                编辑
              </el-button>
              <el-button type="danger" size="small" @click="handleDeleteKB(row.id)">
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="mt-4">
        <el-pagination
          v-model:current-page="kbPageInfo.currentPage"
          v-model:page-size="kbPageInfo.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="kbPageInfo.total"
          @size-change="handleKBSizeChange"
          @current-change="handleKBCurrentChange"
        />
      </div>
    </el-card>

    <el-card v-if="selectedKB">
      <template #header>
        <div class="card-header">
          <span>文档管理 - {{ selectedKB.name }}</span>
          <div class="header-actions">
            <el-button type="success" @click="handleUploadDocument">
              <el-icon><UploadIcon /></el-icon>
              上传文件
            </el-button>
            <el-button type="primary" @click="handleAddDocument">
              <el-icon><Plus /></el-icon>
              新增文档
            </el-button>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="文档列表" name="documents">
          <el-form :inline="true" :model="docSearchForm" class="mb-4">
            <el-form-item label="文档标题">
              <el-input v-model="docSearchForm.title" placeholder="请输入文档标题" clearable />
            </el-form-item>
            <el-form-item label="状态">
              <el-select v-model="docSearchForm.status" placeholder="请选择状态" clearable>
                <el-option label="待处理" value="pending" />
                <el-option label="处理中" value="processing" />
                <el-option label="已完成" value="completed" />
                <el-option label="失败" value="failed" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleDocSearch">
                <el-icon><Search /></el-icon>
                搜索
              </el-button>
              <el-button @click="resetDocSearch">
                <el-icon><Refresh /></el-icon>
                重置
              </el-button>
            </el-form-item>
          </el-form>

          <div class="mb-4" v-if="selectedDocs.length > 0">
            <el-button type="success" :loading="batchProcessing" @click="handleBatchProcess">
              <el-icon><UploadIcon /></el-icon>
              批量处理 ({{ selectedDocs.length }})
            </el-button>
            <el-button @click="selectedDocs = []">取消选择</el-button>
          </div>

          <el-table 
            :data="documents" 
            style="width: 100%" 
            v-loading="docLoading"
            @selection-change="handleDocSelection"
            ref="docTableRef"
          >
            <el-table-column type="selection" width="55" />
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="title" label="文档标题" min-width="150" />
            <el-table-column prop="file_name" label="文件名" min-width="150" show-overflow-tooltip />
            <el-table-column prop="file_type" label="文件类型" width="100" />
            <el-table-column prop="file_size" label="文件大小" width="100" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">
                  {{ getStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="chunk_count" label="分块数量" width="100" />
            <el-table-column prop="created_at" label="创建时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" min-width="300" fixed="right">
              <template #default="{ row }">
                <div class="action-buttons">
                  <el-button type="success" size="small" @click="handleProcessDocument(row)" :disabled="row.status === 'processing' || processingDocumentId === row.id">
                    {{ row.status === 'processing' || processingDocumentId === row.id ? '处理中...' : '处理文档' }}
                  </el-button>
                  <el-button type="info" size="small" @click="handleViewChunks(row)">
                    查看分块
                  </el-button>
                  <el-button type="primary" size="small" @click="handleEditDocument(row)">
                    编辑
                  </el-button>
                  <el-button type="danger" size="small" @click="handleDeleteDocument(row.id)">
                    删除
                  </el-button>
              </div>
              </template>
            </el-table-column>
          </el-table>

          <div class="mt-4">
            <el-pagination
              v-model:current-page="docPageInfo.currentPage"
              v-model:page-size="docPageInfo.pageSize"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next, jumper"
              :total="docPageInfo.total"
              @size-change="handleDocSizeChange"
              @current-change="handleDocCurrentChange"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane label="向量搜索" name="search">
          <el-form :model="searchForm" label-width="100px">
            <el-form-item label="搜索内容">
              <el-input v-model="searchForm.query" type="textarea" :rows="3" placeholder="请输入要搜索的内容" />
            </el-form-item>
            <el-form-item label="返回数量">
              <el-input-number v-model="searchForm.top_k" :min="1" :max="100" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleSearch">
                <el-icon><Search /></el-icon>
                搜索
              </el-button>
            </el-form-item>
          </el-form>

          <div v-if="searchResults.length > 0" class="mt-4">
            <h4>搜索结果</h4>
            <el-card v-for="(result, index) in searchResults" :key="index" class="mt-2">
              <div class="search-result-header">
                <span class="chunk-index">分块 #{{ result.chunk_index }}</span>
                <el-tag v-if="result.similarity" type="success">相似度: {{ (result.similarity * 100).toFixed(2) }}%</el-tag>
              </div>
              <div class="chunk-content">{{ result.content }}</div>
              <div class="chunk-meta mt-2">
                <span>创建时间: {{ formatDate(result.created_at) }}</span>
              </div>
            </el-card>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="kbDialogVisible" :title="kbDialogTitle" width="600px">
      <el-form :model="kbFormData" :rules="kbRules" ref="kbFormRef" label-width="100px">
        <el-form-item label="知识库名称" prop="name">
          <el-input v-model="kbFormData.name" placeholder="请输入知识库名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="kbFormData.description" type="textarea" :rows="3" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="kbFormData.status" placeholder="请选择状态">
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item label="向量维度" prop="vector_dimension">
          <el-input-number v-model="kbFormData.vector_dimension" :min="128" :max="4096" />
        </el-form-item>
        <el-form-item label="Embedding模型">
          <el-select v-model="kbFormData.embedding_model_id" placeholder="请选择Embedding模型" clearable>
            <el-option
              v-for="model in llmModels"
              :key="model.id"
              :label="`${model.model_name} (${model.model_id})`"
              :value="model.id"
            />
          </el-select>
          <div class="form-tip">选择用于向量化的 Embedding 模型，需要先配置该模型的 API Key</div>
        </el-form-item>
        <el-form-item label="搜索模式">
          <el-select v-model="kbFormData.search_mode" placeholder="请选择搜索模式">
            <el-option label="pgvector（推荐）" value="pgvector" />
            <el-option label="LlamaIndex + Qdrant" value="llm_index" />
          </el-select>
          <div class="form-tip">
            <strong>pgvector</strong>: 推荐中小数据量，无需额外服务<br />
            <strong>LlamaIndex</strong>: 大数据量推荐，需要运行 Qdrant
          </div>
        </el-form-item>
        <el-form-item label="公开访问">
          <el-switch v-model="kbFormData.is_public" />
          <div class="form-tip">开启后所有用户都可以访问此知识库</div>
        </el-form-item>
        <el-form-item label="访问级别">
          <el-select v-model="kbFormData.access_level" placeholder="请选择访问级别">
            <el-option label="私有（仅创建者）" value="private" />
            <el-option label="部门内可见" value="dept" />
            <el-option label="完全公开" value="public" />
          </el-select>
          <div class="form-tip">
            <strong>私有</strong>: 仅创建者可以访问<br />
            <strong>部门</strong>: 同部门用户可以访问<br />
            <strong>公开</strong>: 所有人可以访问
          </div>
        </el-form-item>
        <el-form-item label="可见部门" v-if="kbFormData.access_level === 'dept'">
          <el-select
            v-model="kbFormData.visible_department_ids"
            multiple
            placeholder="请选择可见部门"
            style="width: 100%"
          >
            <el-option
              v-for="dept in departments"
              :key="dept.id"
              :label="dept.name"
              :value="dept.id"
            />
          </el-select>
          <div class="form-tip">选择可以访问此知识库的部门，可多选</div>
        </el-form-item>
        <el-form-item label="配置">
          <el-input v-model="kbConfigJson" type="textarea" :rows="4" placeholder="JSON格式配置" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="kbDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleKbSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="docDialogVisible" :title="docDialogTitle" width="600px">
      <el-form :model="docFormData" :rules="docRules" ref="docFormRef" label-width="100px">
        <el-form-item label="文档标题" prop="title">
          <el-input v-model="docFormData.title" placeholder="请输入文档标题" />
        </el-form-item>
        <el-form-item label="文件名">
          <el-input v-model="docFormData.file_name" placeholder="请输入文件名" />
        </el-form-item>
        <el-form-item label="文件类型">
          <el-input v-model="docFormData.file_type" placeholder="请输入文件类型" />
        </el-form-item>
        <el-form-item label="文件大小">
          <el-input-number v-model="docFormData.file_size" :min="0" />
        </el-form-item>
        <el-form-item label="文件路径">
          <el-input v-model="docFormData.file_path" placeholder="请输入文件路径" />
        </el-form-item>
        <el-form-item label="文档内容" prop="content">
          <el-input v-model="docFormData.content" type="textarea" :rows="10" placeholder="请输入文档内容" />
        </el-form-item>
        <el-form-item label="元数据">
          <el-input v-model="docMetadataJson" type="textarea" :rows="4" placeholder="JSON格式元数据" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="docDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleDocSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="uploadDialogVisible" title="上传文档" width="500px">
      <el-upload
        ref="uploadFile"
        class="doc-upload"
        drag
        :auto-upload="false"
        :limit="1"
        accept=".pdf,.docx,.doc,.xlsx,.xls,.pptx,.ppt,.txt,.md,.markdown,.py,.js,.html,.css,.json,.yaml,.yml"
        :on-change="handleFileChange"
        :on-exceed="handleExceed"
      >
        <el-icon class="el-icon--upload"><UploadIcon /></el-icon>
        <div class="el-upload__text">
          将文档拖到此处，或<em>点击上传</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            <strong>支持格式：</strong>
            <div style="margin-top: 8px;">
              <el-tag type="info" size="small" style="margin: 2px;">PDF (.pdf)</el-tag>
              <el-tag type="info" size="small" style="margin: 2px;">Word (.docx)</el-tag>
              <el-tag type="info" size="small" style="margin: 2px;">Excel (.xlsx)</el-tag>
              <el-tag type="info" size="small" style="margin: 2px;">PPT (.pptx)</el-tag>
              <br/>
              <el-tag type="success" size="small" style="margin: 2px;">文本 (.txt, .md)</el-tag>
              <el-tag type="success" size="small" style="margin: 2px;">代码 (.py, .js, .html)</el-tag>
            </div>
          </div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="uploadDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploadLoading" :disabled="!selectedUploadFile" @click="handleUpload">
          上传
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="chunksDialogVisible" title="文档分块" width="80%">
      <el-table :data="chunks" style="width: 100%" v-loading="chunksLoading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="chunk_index" label="分块索引" width="100" />
        <el-table-column prop="content" label="内容" min-width="400" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" size="small" @click="handleDeleteChunk(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="chunksDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Plus, Search, Refresh, Edit, Delete, Upload as UploadIcon } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getRAGKnowledgeBases,
  createRAGKnowledgeBase,
  updateRAGKnowledgeBase,
  deleteRAGKnowledgeBase,
  getRAGDocuments,
  createRAGDocument,
  updateRAGDocument,
  deleteRAGDocument,
  processRAGDocument,
  batchProcessRAGDocuments,
  getRAGDocumentChunks,
  deleteRAGChunk,
  searchRAG,
  uploadRAGDocument,
  getDepartments
} from '@/api/agent'
import { getModelList } from '@/api/llm'

const kbLoading = ref(false)
const docLoading = ref(false)
const chunksLoading = ref(false)
const knowledgeBases = ref([])
const documents = ref([])
const chunks = ref([])
const selectedKB = ref(null)
const activeTab = ref('documents')
const searchResults = ref([])
const llmModels = ref([])
const uploadLoading = ref(false)
const uploadDialogVisible = ref(false)
const uploadFile = ref(null)
const selectedUploadFile = ref(null)
const processingDocumentId = ref(null)
const batchProcessing = ref(false)
const selectedDocs = ref([])
const docTableRef = ref(null)

const kbPageInfo = reactive({
  currentPage: 1,
  pageSize: 10,
  total: 0
})

const docPageInfo = reactive({
  currentPage: 1,
  pageSize: 10,
  total: 0
})

const docSearchForm = reactive({
  title: '',
  status: ''
})

const searchForm = reactive({
  query: '',
  top_k: 5
})

const kbDialogVisible = ref(false)
const kbDialogTitle = ref('新增知识库')
const kbFormRef = ref(null)
const kbFormData = reactive({
  id: null,
  name: '',
  description: '',
  status: 'active',
  vector_dimension: 1024,
  config: {},
  embedding_model_id: null,
  search_mode: 'pgvector',
  is_public: false,
  access_level: 'private',
  visible_department_ids: []
})

const departments = ref([])

const kbConfigJson = computed({
  get: () => JSON.stringify(kbFormData.config, null, 2),
  set: (val) => {
    try {
      kbFormData.config = JSON.parse(val)
    } catch (e) {
      // ignore parse error
    }
  }
})

const kbRules = {
  name: [{ required: true, message: '请输入知识库名称', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
}

const docDialogVisible = ref(false)
const docDialogTitle = ref('新增文档')
const docFormRef = ref(null)
const docFormData = reactive({
  id: null,
  knowledge_base_id: null,
  title: '',
  file_name: '',
  file_type: '',
  file_size: null,
  file_path: '',
  content: '',
  metadata: {}
})

const docMetadataJson = computed({
  get: () => JSON.stringify(docFormData.metadata, null, 2),
  set: (val) => {
    try {
      docFormData.metadata = JSON.parse(val)
    } catch (e) {
      // ignore parse error
    }
  }
})

const docRules = {
  title: [{ required: true, message: '请输入文档标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入文档内容', trigger: 'blur' }]
}

const chunksDialogVisible = ref(false)

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

const getStatusType = (status) => {
  const typeMap = {
    pending: 'info',
    processing: 'warning',
    completed: 'success',
    failed: 'danger'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const textMap = {
    pending: '待处理',
    processing: '处理中',
    completed: '已完成',
    failed: '失败'
  }
  return textMap[status] || status
}

const fetchKnowledgeBases = async () => {
  kbLoading.value = true
  try {
    const res = await getRAGKnowledgeBases({
      skip: (kbPageInfo.currentPage - 1) * kbPageInfo.pageSize,
      limit: kbPageInfo.pageSize
    })
    if (res.data) {
      knowledgeBases.value = res.data.items || res.data
      kbPageInfo.total = res.data.total || knowledgeBases.value.length
    }
  } catch (error) {
    ElMessage.error('获取知识库列表失败')
    console.error(error)
  } finally {
    kbLoading.value = false
  }
}

const fetchDocuments = async () => {
  if (!selectedKB.value) return
  docLoading.value = true
  try {
    const res = await getRAGDocuments({
      knowledge_base_id: selectedKB.value.id,
      skip: (docPageInfo.currentPage - 1) * docPageInfo.pageSize,
      limit: docPageInfo.pageSize,
      ...docSearchForm
    })
    if (res.data) {
      documents.value = res.data.items || res.data
      docPageInfo.total = res.data.total || documents.value.length
    }
  } catch (error) {
    ElMessage.error('获取文档列表失败')
    console.error(error)
  } finally {
    docLoading.value = false
  }
}

const handleKBSizeChange = (size) => {
  kbPageInfo.pageSize = size
  fetchKnowledgeBases()
}

const handleKBCurrentChange = (current) => {
  kbPageInfo.currentPage = current
  fetchKnowledgeBases()
}

const handleDocSizeChange = (size) => {
  docPageInfo.pageSize = size
  fetchDocuments()
}

const handleDocCurrentChange = (current) => {
  docPageInfo.currentPage = current
  fetchDocuments()
}

const handleAddKB = () => {
  kbDialogTitle.value = '新增知识库'
  kbFormData.id = null
  kbFormData.name = ''
  kbFormData.description = ''
  kbFormData.status = 'active'
  kbFormData.vector_dimension = 1024
  kbFormData.config = {}
  kbFormData.embedding_model_id = null
  kbFormData.search_mode = 'pgvector'
  kbFormData.is_public = false
  kbFormData.access_level = 'private'
  kbFormData.visible_department_ids = []
  kbDialogVisible.value = true
}

const handleEditKB = (row) => {
  kbDialogTitle.value = '编辑知识库'
  kbFormData.id = row.id
  kbFormData.name = row.name
  kbFormData.description = row.description
  kbFormData.status = row.status
  kbFormData.vector_dimension = row.vector_dimension
  kbFormData.config = row.config || {}
  kbFormData.embedding_model_id = row.embedding_model_id || null
  kbFormData.search_mode = row.search_mode || 'pgvector'
  kbFormData.is_public = row.is_public || false
  kbFormData.access_level = row.access_level || 'private'
  kbFormData.visible_department_ids = row.visible_department_ids || []
  kbDialogVisible.value = true
}

const handleKbSubmit = async () => {
  if (!kbFormRef.value) return
  await kbFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        if (kbFormData.id) {
          await updateRAGKnowledgeBase(kbFormData.id, kbFormData)
          ElMessage.success('编辑成功')
        } else {
          await createRAGKnowledgeBase(kbFormData)
          ElMessage.success('新增成功')
        }
        kbDialogVisible.value = false
        fetchKnowledgeBases()
      } catch (error) {
        ElMessage.error('操作失败')
        console.error(error)
      }
    }
  })
}

const handleDeleteKB = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该知识库吗？', '提示', { type: 'warning' })
    await deleteRAGKnowledgeBase(id)
    ElMessage.success('删除成功')
    if (selectedKB.value && selectedKB.value.id === id) {
      selectedKB.value = null
    }
    fetchKnowledgeBases()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

const handleSelectKB = (row) => {
  selectedKB.value = row
  docPageInfo.currentPage = 1
  fetchDocuments()
}

const handleUploadDocument = () => {
  if (!selectedKB.value) {
    ElMessage.warning('请先选择一个知识库')
    return
  }
  uploadDialogVisible.value = true
}

const handleFileChange = (file) => {
  selectedUploadFile.value = file.raw
}

const handleExceed = () => {
  ElMessage.warning('只能选择一个文件')
}

const handleUpload = async () => {
  if (!selectedUploadFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  
  uploadLoading.value = true
  try {
    await uploadRAGDocument(selectedKB.value.id, selectedUploadFile.value)
    ElMessage.success('上传成功')
    uploadDialogVisible.value = false
    fetchDocuments()
  } catch (error) {
    ElMessage.error('上传失败: ' + (error.response?.data?.msg || error.message))
  } finally {
    uploadLoading.value = false
  }
}

const handleAddDocument = () => {
  if (!selectedKB.value) {
    ElMessage.warning('请先选择一个知识库')
    return
  }
  docDialogTitle.value = '新增文档'
  docFormData.id = null
  docFormData.knowledge_base_id = selectedKB.value.id
  docFormData.title = ''
  docFormData.file_name = ''
  docFormData.file_type = ''
  docFormData.file_size = null
  docFormData.file_path = ''
  docFormData.content = ''
  docFormData.metadata = {}
  docDialogVisible.value = true
}

const handleEditDocument = (row) => {
  docDialogTitle.value = '编辑文档'
  docFormData.id = row.id
  docFormData.knowledge_base_id = row.knowledge_base_id
  docFormData.title = row.title
  docFormData.file_name = row.file_name
  docFormData.file_type = row.file_type
  docFormData.file_size = row.file_size
  docFormData.file_path = row.file_path
  docFormData.content = row.content
  docFormData.metadata = row.metadata || {}
  docDialogVisible.value = true
}

const handleDocSubmit = async () => {
  if (!docFormRef.value) return
  await docFormRef.value.validate(async (valid) => {
    if (valid) {
      try {
        if (docFormData.id) {
          await updateRAGDocument(docFormData.id, docFormData)
          ElMessage.success('编辑成功')
        } else {
          await createRAGDocument(docFormData)
          ElMessage.success('新增成功')
        }
        docDialogVisible.value = false
        fetchDocuments()
      } catch (error) {
        ElMessage.error('操作失败')
        console.error(error)
      }
    }
  })
}

const handleDeleteDocument = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该文档吗？', '提示', { type: 'warning' })
    await deleteRAGDocument(id)
    ElMessage.success('删除成功')
    fetchDocuments()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

const handleDocSelection = (selection) => {
    selectedDocs.value = selection
}

const handleBatchProcess = async () => {
    if (selectedDocs.value.length === 0) {
        ElMessage.warning('请选择要处理的文档')
        return
    }

    try {
        await ElMessageBox.prompt('请选择文档切片策略', '批量处理文档', {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            inputPattern: /^(smart|paragraph|simple)$/,
            inputErrorMessage: '请选择有效的切片策略',
            inputType: 'select',
            inputValue: 'smart',
            inputOptions: [
                { label: '智能切片（推荐）', value: 'smart' },
                { label: '按段落', value: 'paragraph' },
                { label: '简单切片', value: 'simple' }
            ]
        }).then(async ({ value: splitStrategy }) => {
            await ElMessageBox.prompt('请输入切片大小（字符数）', '批量处理文档', {
                confirmButtonText: '确定',
                cancelButtonText: '取消',
                inputValue: '500',
                inputPattern: /^\d+$/,
                inputErrorMessage: '请输入有效的数字'
            }).then(async ({ value: chunkSizeStr }) => {
                const chunkSize = parseInt(chunkSizeStr)
                await ElMessageBox.prompt('请输入重叠大小（字符数）', '批量处理文档', {
                    confirmButtonText: '确定',
                    cancelButtonText: '取消',
                    inputValue: '50',
                    inputPattern: /^\d+$/,
                    inputErrorMessage: '请输入有效的数字'
                }).then(async ({ value: chunkOverlapStr }) => {
                    const chunkOverlap = parseInt(chunkOverlapStr)
                    
                    batchProcessing.value = true
                    
                    try {
                        ElMessage.info(`正在处理 ${selectedDocs.value.length} 个文档，这可能需要一段时间，请耐心等待...`)
                        
                        const docIds = selectedDocs.value.map(doc => doc.id)
                        const res = await batchProcessRAGDocuments(docIds, chunkSize, chunkOverlap, splitStrategy)
                        
                        if (res.data) {
                            const { total, success, failed, results, errors } = res.data
                            
                            ElMessage.success(`批量处理完成！共 ${total} 个，成功 ${success} 个，失败 ${failed} 个`)
                            
                            if (errors.length > 0) {
                                ElMessage.warning(`部分文档处理失败，请查看控制台详情`)
                                console.error('失败的文档:', errors)
                            }
                        }
                        
                        fetchDocuments()
                        selectedDocs.value = []
                    } finally {
                        batchProcessing.value = false
                    }
                }).catch(() => {
                    ElMessage.info('已取消')
                })
            }).catch(() => {
                ElMessage.info('已取消')
            })
        }).catch(() => {
            ElMessage.info('已取消')
        })
    } catch (error) {
        ElMessage.error('批量处理失败: ' + (error.response?.data?.msg || error.message))
        console.error(error)
        batchProcessing.value = false
    }
}

const handleProcessDocument = async (row) => {
    try {
        await ElMessageBox.prompt('请选择文档切片策略', '处理文档', {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            inputPattern: /^(smart|paragraph|simple)$/,
            inputErrorMessage: '请选择有效的切片策略',
            inputType: 'select',
            inputValue: 'smart',
            inputOptions: [
                { label: '智能切片（推荐）', value: 'smart' },
                { label: '按段落', value: 'paragraph' },
                { label: '简单切片', value: 'simple' }
            ]
        }).then(async ({ value: splitStrategy }) => {
            await ElMessageBox.prompt('请输入切片大小（字符数）', '处理文档', {
                confirmButtonText: '确定',
                cancelButtonText: '取消',
                inputValue: '500',
                inputPattern: /^\d+$/,
                inputErrorMessage: '请输入有效的数字'
            }).then(async ({ value: chunkSizeStr }) => {
                const chunkSize = parseInt(chunkSizeStr)
                await ElMessageBox.prompt('请输入重叠大小（字符数）', '处理文档', {
                    confirmButtonText: '确定',
                    cancelButtonText: '取消',
                    inputValue: '50',
                    inputPattern: /^\d+$/,
                    inputErrorMessage: '请输入有效的数字'
                }).then(async ({ value: chunkOverlapStr }) => {
                    const chunkOverlap = parseInt(chunkOverlapStr)
                    
                    processingDocumentId.value = row.id
                    
                    try {
                        ElMessage.info('正在处理文档，这可能需要一段时间，请耐心等待...')
                        
                        await processRAGDocument(row.id, chunkSize, chunkOverlap, splitStrategy)
                        
                        ElMessage.success('文档处理成功！')
                        fetchDocuments()
                    } finally {
                        processingDocumentId.value = null
                    }
                }).catch(() => {
                    ElMessage.info('已取消')
                })
            }).catch(() => {
                ElMessage.info('已取消')
            })
        }).catch(() => {
            ElMessage.info('已取消')
        })
    } catch (error) {
        ElMessage.error('处理失败: ' + (error.response?.data?.msg || error.message))
        console.error(error)
        processingDocumentId.value = null
    }
}

const handleViewChunks = async (row) => {
  chunksLoading.value = true
  try {
    const res = await getRAGDocumentChunks(row.id)
    if (res.data) {
      chunks.value = res.data.items || res.data
    }
    chunksDialogVisible.value = true
  } catch (error) {
    ElMessage.error('获取分块失败')
    console.error(error)
  } finally {
    chunksLoading.value = false
  }
}

const handleDeleteChunk = async (id) => {
  try {
    await ElMessageBox.confirm('确定要删除该分块吗？', '提示', { type: 'warning' })
    await deleteRAGChunk(id)
    ElMessage.success('删除成功')
    chunks.value = chunks.value.filter(c => c.id !== id)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

const handleDocSearch = () => {
  docPageInfo.currentPage = 1
  fetchDocuments()
}

const resetDocSearch = () => {
  docSearchForm.title = ''
  docSearchForm.status = ''
  handleDocSearch()
}

const handleSearch = async () => {
  if (!selectedKB.value) {
    ElMessage.warning('请先选择一个知识库')
    return
  }
  if (!searchForm.query.trim()) {
    ElMessage.warning('请输入搜索内容')
    return
  }
  try {
    const res = await searchRAG({
      knowledge_base_id: selectedKB.value.id,
      query: searchForm.query,
      top_k: searchForm.top_k
    })
    if (res.data) {
      searchResults.value = res.data.results || []
      ElMessage.success(`找到 ${searchResults.value.length} 条结果`)
    }
  } catch (error) {
    ElMessage.error('搜索失败')
    console.error(error)
  }
}

const fetchLLMModels = async () => {
  try {
    const res = await getModelList({ page: 1, page_size: 100 })
    if (res.data) {
      llmModels.value = res.data.items || res.data
    }
  } catch (error) {
    console.error('获取模型列表失败:', error)
  }
}

const fetchDepartments = async () => {
  try {
    const res = await getDepartments({ page: 1, page_size: 100 })
    if (res.data) {
      departments.value = res.data.items || res.data
    }
  } catch (error) {
    console.error('获取部门列表失败:', error)
  }
}

onMounted(() => {
  fetchKnowledgeBases()
  fetchLLMModels()
  fetchDepartments()
})
</script>

<style scoped>
.rag-container {
  padding: 0;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 10px;
}
.mb-4 {
  margin-bottom: 16px;
}
.mt-2 {
  margin-top: 8px;
}
.mt-4 {
  margin-top: 16px;
}
.action-buttons {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  align-items: center;
  gap: 4px;
}
.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.search-result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.chunk-index {
  font-weight: bold;
  color: #409eff;
}
.chunk-content {
  line-height: 1.6;
  color: #333;
  word-break: break-word;
}
.chunk-meta {
  font-size: 12px;
  color: #999;
}
</style>


