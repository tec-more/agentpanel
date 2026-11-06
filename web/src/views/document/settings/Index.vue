<template>
  <div class="document-settings">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>文档设置</span>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <!-- 基本设置 -->
        <el-tab-pane label="基本设置" name="basic">
          <el-form :model="basicConfig" label-width="150px" style="max-width: 600px; margin-top: 20px;">
            <el-form-item label="存储路径">
              <el-input v-model="basicConfig.storage_path" />
            </el-form-item>
            <el-form-item label="允许的文件类型">
              <el-select
                v-model="basicConfig.allowed_types"
                multiple
                style="width: 100%"
              >
                <el-option label="PDF" value="pdf" />
                <el-option label="Word" value="docx" />
                <el-option label="Excel" value="xlsx" />
                <el-option label="PPT" value="pptx" />
                <el-option label="图片" value="image" />
                <el-option label="文本" value="txt" />
                <el-option label="Markdown" value="md" />
              </el-select>
            </el-form-item>
            <el-form-item label="单个文件大小限制">
              <el-input-number v-model="basicConfig.max_file_size" :min="1" />
              <span style="margin-left: 8px;">MB</span>
            </el-form-item>
            <el-form-item label="自动备份">
              <el-switch v-model="basicConfig.auto_backup" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveBasicConfig">保存设置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- RAG 集成设置 -->
        <el-tab-pane label="RAG 集成" name="rag">
          <el-form :model="ragConfig" label-width="150px" style="max-width: 600px; margin-top: 20px;">
            <el-form-item label="启用 RAG 集成">
              <el-switch v-model="ragConfig.enabled" />
            </el-form-item>
            <el-form-item label="自动关联知识库">
              <el-switch
                v-model="ragConfig.auto_link"
                :disabled="!ragConfig.enabled"
              />
            </el-form-item>
            <el-form-item label="默认知识库">
              <el-select
                v-model="ragConfig.default_knowledge_base_id"
                placeholder="选择默认知识库"
                clearable
                :disabled="!ragConfig.enabled"
                style="width: 100%"
              >
                <el-option
                  v-for="kb in knowledgeBases"
                  :key="kb.id"
                  :label="kb.name"
                  :value="kb.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="分块大小">
              <el-input-number
                v-model="ragConfig.chunk_size"
                :min="100"
                :max="10000"
                :step="100"
              />
              <span style="margin-left: 8px;">字符</span>
            </el-form-item>
            <el-form-item label="分块重叠">
              <el-input-number
                v-model="ragConfig.chunk_overlap"
                :min="0"
                :max="1000"
                :step="50"
              />
              <span style="margin-left: 8px;">字符</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveRagConfig">保存设置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 权限设置 -->
        <el-tab-pane label="权限设置" name="permission">
          <el-form :model="permConfig" label-width="150px" style="max-width: 600px; margin-top: 20px;">
            <el-form-item label="默认可见性">
              <el-select v-model="permConfig.default_visibility">
                <el-option label="私有" value="private" />
                <el-option label="部门" value="dept" />
                <el-option label="公开" value="public" />
              </el-select>
            </el-form-item>
            <el-form-item label="允许分享">
              <el-switch v-model="permConfig.allow_share" />
            </el-form-item>
            <el-form-item label="允许下载">
              <el-switch v-model="permConfig.allow_download" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="savePermConfig">保存设置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'

const activeTab = ref('basic')

const basicConfig = reactive({
  storage_path: '/data/documents',
  allowed_types: ['pdf', 'docx', 'xlsx', 'pptx', 'image', 'txt', 'md'],
  max_file_size: 50,
  auto_backup: true
})

const ragConfig = reactive({
  enabled: true,
  auto_link: false,
  default_knowledge_base_id: null,
  chunk_size: 1000,
  chunk_overlap: 200
})

const knowledgeBases = ref([])

const permConfig = reactive({
  default_visibility: 'private',
  allow_share: true,
  allow_download: true
})

const saveBasicConfig = async () => {
  ElMessage.success('基本设置保存成功')
}

const saveRagConfig = async () => {
  ElMessage.success('RAG 集成设置保存成功')
}

const savePermConfig = async () => {
  ElMessage.success('权限设置保存成功')
}

onMounted(() => {
  // TODO: 加载实际配置
})
</script>

<style lang="scss" scoped>
.document-settings {
  padding: 20px;
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>
