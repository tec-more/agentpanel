<template>
  <div class="joke-translator">
    <el-card class="main-card">
      <template #header>
        <div class="card-header">
          <span>🎭 智能笑话翻译</span>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12">
          <el-card shadow="hover" class="input-card">
            <template #header>
              <div class="card-title">
                <span>📝 输入笑话</span>
              </div>
            </template>
            
            <el-form :model="translateForm" label-width="80px">
              <el-form-item label="源语言">
                <el-select v-model="translateForm.source_lang" placeholder="请选择源语言" style="width: 100%">
                  <el-option
                    v-for="lang in languages"
                    :key="lang.code"
                    :label="lang.name"
                    :value="lang.code"
                  />
                </el-select>
              </el-form-item>
              
              <el-form-item label="目标语言">
                <el-select v-model="translateForm.target_lang" placeholder="请选择目标语言" style="width: 100%">
                  <el-option
                    v-for="lang in languages.filter(l => l.code !== 'auto')"
                    :key="lang.code"
                    :label="lang.name"
                    :value="lang.code"
                  />
                </el-select>
              </el-form-item>
              
              <el-form-item label="笑话内容">
                <el-input
                  v-model="translateForm.text"
                  type="textarea"
                  :rows="8"
                  placeholder="请输入要翻译的笑话..."
                  clearable
                />
              </el-form-item>
              
              <el-form-item>
                <el-button 
                  type="primary" 
                  @click="handleTranslate" 
                  :loading="translating"
                  :disabled="!translateForm.text"
                >
                  <el-icon><Position /></el-icon>
                  开始翻译
                </el-button>
                <el-button @click="handleClear">
                  <el-icon><Delete /></el-icon>
                  清空
                </el-button>
              </el-form-item>
            </el-form>
          </el-card>
        </el-col>
        
        <el-col :span="12">
          <el-card shadow="hover" class="output-card">
            <template #header>
              <div class="card-title">
                <span>🎯 翻译结果</span>
              </div>
            </template>
            
            <div v-if="result" class="result-container">
              <div class="result-item">
                <div class="result-label">翻译后的笑话：</div>
                <div class="result-content">{{ result.translation }}</div>
              </div>
              
              <el-divider />
              
              <div class="result-meta">
                <el-tag type="info">{{ getLanguageName(result.source_lang) }}</el-tag>
                <el-icon><Right /></el-icon>
                <el-tag type="success">{{ getLanguageName(result.target_lang) }}</el-tag>
              </div>
            </div>
            
            <el-empty v-else description="暂无翻译结果" />
          </el-card>
        </el-col>
      </el-row>
    </el-card>
    
    <el-card class="examples-card">
      <template #header>
        <div class="card-header">
          <span>💡 笑话示例</span>
          <el-button type="primary" size="small" @click="loadExamples">
            <el-icon><Refresh /></el-icon>
            刷新示例
          </el-button>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="12" v-for="example in examples" :key="example.id">
          <el-card shadow="hover" class="example-card" @click="useExample(example)">
            <div class="example-category">
              <el-tag type="warning">{{ example.category }}</el-tag>
            </div>
            <div class="example-text">{{ example.text }}</div>
            <div class="example-langs">
              <el-tag size="small">{{ getLanguageName(example.source_lang) }}</el-tag>
              <el-icon><Right /></el-icon>
              <el-tag size="small" type="success">{{ getLanguageName(example.target_lang) }}</el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Position, Delete, Right, Refresh } from '@element-plus/icons-vue'
import request from '@/utils/request'

const translateForm = ref({
  text: '',
  source_lang: 'auto',
  target_lang: 'en',
  model_name: 'gpt-3.5-turbo'
})

const result = ref(null)
const translating = ref(false)
const languages = ref([])
const examples = ref([])

const loadLanguages = async () => {
  try {
    const res = await request.get('/api/v1/agent/joke/languages')
    if (res.data) {
      languages.value = res.data
    }
  } catch (error) {
    ElMessage.error('加载语言列表失败')
  }
}

const loadExamples = async () => {
  try {
    const res = await request.get('/api/v1/agent/joke/examples')
    if (res.data) {
      examples.value = res.data
    }
  } catch (error) {
    ElMessage.error('加载示例失败')
  }
}

const handleTranslate = async () => {
  if (!translateForm.value.text) {
    ElMessage.warning('请输入要翻译的笑话')
    return
  }
  
  translating.value = true
  result.value = null
  
  try {
    const res = await request.post('/api/v1/agent/joke/translate', translateForm.value)
    if (res.success) {
      result.value = res
      ElMessage.success('翻译成功')
    } else {
      ElMessage.error(res.message || '翻译失败')
    }
  } catch (error) {
    ElMessage.error('翻译失败：' + error.message)
  } finally {
    translating.value = false
  }
}

const handleClear = () => {
  translateForm.value.text = ''
  result.value = null
}

const useExample = (example) => {
  translateForm.value.text = example.text
  translateForm.value.source_lang = example.source_lang
  translateForm.value.target_lang = example.target_lang
}

const getLanguageName = (code) => {
  const lang = languages.value.find(l => l.code === code)
  return lang ? lang.name : code
}

onMounted(() => {
  loadLanguages()
  loadExamples()
})
</script>

<style scoped>
.joke-translator {
  padding: 20px;
}

.main-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 18px;
  font-weight: bold;
}

.card-title {
  font-size: 16px;
  font-weight: bold;
}

.input-card,
.output-card {
  height: 100%;
  min-height: 500px;
}

.result-container {
  padding: 20px;
}

.result-item {
  margin-bottom: 20px;
}

.result-label {
  font-weight: bold;
  margin-bottom: 10px;
  color: #409eff;
}

.result-content {
  line-height: 1.8;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
  white-space: pre-wrap;
}

.result-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: center;
}

.examples-card {
  margin-top: 20px;
}

.example-card {
  cursor: pointer;
  transition: all 0.3s;
  margin-bottom: 20px;
}

.example-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.example-category {
  margin-bottom: 10px;
}

.example-text {
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 10px;
  color: #606266;
}

.example-langs {
  display: flex;
  align-items: center;
  gap: 5px;
}
</style>


