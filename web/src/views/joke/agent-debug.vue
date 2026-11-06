<template>
  <div class="joke-agent-debug">
    <el-card class="main-card">
      <template #header>
        <div class="card-header">
          <span>🎭 笑话智能体调试</span>
          <el-button type="primary" size="small" @click="loadAgentInfo">
            <el-icon><Refresh /></el-icon>
            刷新信息
          </el-button>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col :span="8">
          <el-card shadow="hover" class="config-card">
            <template #header>
              <div class="card-title">
                <span>⚙️ 配置</span>
              </div>
            </template>
            
            <el-form :model="configForm" label-width="100px">
              <el-form-item label="智能体ID">
                <el-input-number 
                  v-model="configForm.agent_id" 
                  :min="1" 
                  placeholder="请输入智能体ID"
                  @change="loadAgentInfo"
                />
              </el-form-item>
              
              <el-form-item label="大模型">
                <el-select v-model="configForm.model_name" placeholder="请选择模型" style="width: 100%">
                  <el-option label="GPT-3.5 Turbo" value="gpt-3.5-turbo" />
                  <el-option label="GPT-4" value="gpt-4" />
                  <el-option label="GPT-4 Turbo" value="gpt-4-turbo" />
                  <el-option label="Claude 3 Sonnet" value="claude-3-sonnet" />
                  <el-option label="Claude 3 Opus" value="claude-3-opus" />
                </el-select>
              </el-form-item>
              
              <el-form-item label="启用RAG">
                <el-switch v-model="configForm.enable_rag" />
              </el-form-item>
              
              <el-divider />
              
              <div v-if="agentInfo" class="agent-info">
                <div class="info-item">
                  <span class="label">名称：</span>
                  <span class="value">{{ agentInfo.agent?.name }}</span>
                </div>
                <div class="info-item">
                  <span class="label">状态：</span>
                  <el-tag :type="agentInfo.agent?.status === 'active' ? 'success' : 'info'">
                    {{ agentInfo.agent?.status }}
                  </el-tag>
                </div>
                <div class="info-item">
                  <span class="label">技能数：</span>
                  <span class="value">{{ agentInfo.skills?.length || 0 }}</span>
                </div>
                <div class="info-item">
                  <span class="label">记忆数：</span>
                  <span class="value">{{ agentInfo.memory_stats?.total || 0 }}</span>
                </div>
                <div class="info-item">
                  <span class="label">大模型：</span>
                  <span class="value">{{ agentInfo.llm_model?.model_name || '未设置' }}</span>
                </div>
             
                
                <el-divider />
                
                <div class="skills-list">
                  <div class="section-title">关联技能：</div>
                  <el-tag 
                    v-for="skill in agentInfo.skills" 
                    :key="skill.id"
                    type="info"
                    style="margin: 5px"
                  >
                    {{ skill.name }} ({{ skill.type }})
                  </el-tag>
                  <el-empty v-if="!agentInfo.skills || agentInfo.skills.length === 0" description="暂无关联技能" :image-size="60" />
                </div>
              </div>
            </el-form>
          </el-card>
        </el-col>
        
        <el-col :span="16">
          <el-card shadow="hover" class="chat-card">
            <template #header>
              <div class="card-title">
                <span>💬 对话测试</span>
              </div>
            </template>
            
            <div class="chat-container">
              <div class="chat-messages" ref="chatMessages">
                <div 
                  v-for="(message, index) in messages" 
                  :key="index"
                  :class="['message', message.role]"
                >
                  <div class="message-content">
                    <div class="message-role">{{ message.role === 'user' ? '用户' : 'AI' }}</div>
                    <div class="message-text">{{ message.content }}</div>
                  </div>
                </div>
              </div>
              
              <div class="chat-input">
                <el-input
                  v-model="inputText"
                  type="textarea"
                  :rows="3"
                  placeholder="请输入要测试的内容..."
                  @keydown.ctrl.enter="handleSend"
                />
                <div class="input-actions">
                  <el-button 
                    type="primary" 
                    @click="handleSend" 
                    :loading="sending"
                    :disabled="!inputText"
                  >
                    <el-icon><Position /></el-icon>
                    发送 (Ctrl+Enter)
                  </el-button>
                  <el-button @click="handleClear">
                    <el-icon><Delete /></el-icon>
                    清空
                  </el-button>
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
    
    <el-card class="debug-card" v-if="lastResult">
      <template #header>
        <div class="card-header">
          <span>🔍 调试信息</span>
          <el-button type="danger" size="small" @click="lastResult = null">
            <el-icon><Close /></el-icon>
            关闭
          </el-button>
        </div>
      </template>
      
      <el-descriptions :column="2" border>
        <el-descriptions-item label="成功">
          <el-tag :type="lastResult.success ? 'success' : 'danger'">
            {{ lastResult.success ? '是' : '否' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="消息">
          {{ lastResult.message || '无' }}
        </el-descriptions-item>
      </el-descriptions>
      
      <el-divider />
      
      <div v-if="lastResult.rag_context" class="debug-section">
        <div class="section-title">RAG 上下文</div>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="相关记忆数">
            {{ lastResult.rag_context.memory_count || 0 }}
          </el-descriptions-item>
        </el-descriptions>
        <div v-if="lastResult.rag_context.relevant_memories && lastResult.rag_context.relevant_memories.length > 0" class="memories-list">
          <div v-for="(memory, index) in lastResult.rag_context.relevant_memories" :key="index" class="memory-item">
            <el-tag size="small">记忆 {{ index + 1 }}</el-tag>
            <div class="memory-content">{{ memory }}</div>
          </div>
        </div>
      </div>
      
      <el-divider />
      
      <div v-if="lastResult.skill_result" class="debug-section">
        <div class="section-title">技能执行结果</div>
        <pre class="json-display">{{ JSON.stringify(lastResult.skill_result, null, 2) }}</pre>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Position, Delete, Close } from '@element-plus/icons-vue'
import request from '@/utils/request'

const configForm = ref({
  agent_id: null,
  model_name: 'gpt-3.5-turbo',
  enable_rag: true
})

const agentInfo = ref(null)
const inputText = ref('')
const messages = ref([])
const sending = ref(false)
const lastResult = ref(null)
const chatMessages = ref(null)

const loadAgentInfo = async () => {
  if (!configForm.value.agent_id) {
    agentInfo.value = null
    return
  }
  
  try {
    const res = await request.get(`/api/v1/agent/joke-agent/debug/${configForm.value.agent_id}`)
    if (res.data) {
      agentInfo.value = res.data
    }
  } catch (error) {
    ElMessage.error('加载智能体信息失败')
    console.error(error)
  }
}

const handleSend = async () => {
  if (!inputText.value) {
    ElMessage.warning('请输入内容')
    return
  }
  
  const userMessage = inputText.value
  messages.value.push({
    role: 'user',
    content: userMessage
  })
  
  inputText.value = ''
  sending.value = true
  
  await scrollToBottom()
  
  
  try {
    const res = await request.post('/api/v1/agent/joke-agent/chat', {
      text: userMessage,
      agent_id: configForm.value.agent_id,
      enable_rag: configForm.value.enable_rag,
      model_name: configForm.value.model_name
    })
    
    if (res.success) {
      messages.value.push({
        role: 'assistant',
        content: res.result || '无回复'
      })
      
      lastResult.value = res
      
      await scrollToBottom()
    } else {
      ElMessage.error(res.message || '处理失败')
    }
  } catch (error) {
    ElMessage.error('处理失败：' + error.message)
    console.error(error)
  } finally {
    sending.value = false
  }
}

const handleClear = () => {
  messages.value = []
  lastResult.value = null
}

const scrollToBottom = async () => {
  await nextTick()
  if (chatMessages.value) {
    chatMessages.value.scrollTop = chatMessages.value.scrollHeight
  }
}

onMounted(() => {
  if (configForm.value.agent_id) {
    loadAgentInfo()
  }
})
</script>

<style scoped>
.joke-agent-debug {
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

.config-card,
.chat-card {
  height: 100%;
  min-height: 600px;
}

.agent-info {
  padding: 10px 0;
}

.info-item {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.info-item .label {
  font-weight: bold;
  margin-right: 10px;
  min-width: 80px;
}

.info-item .value {
  color: #606266;
}

.skills-list {
  margin-top: 15px;
}

.section-title {
  font-weight: bold;
  margin-bottom: 10px;
  color: #409eff;
}

.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 20px;
  overflow: hidden;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 20px;
  min-height: 300px;
  max-height: 500px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 15px;
  scrollbar-width: thin;
  scrollbar-color: #c0c4cc #f5f7fa;
}

.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.chat-messages::-webkit-scrollbar-track {
  background: #f5f7fa;
  border-radius: 3px;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: #c0c4cc;
  border-radius: 3px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: #909399;
}

.message {
  margin-bottom: 15px;
}

.message.user {
  display: flex;
  justify-content: flex-end;
}

.message.assistant {
  display: flex;
  justify-content: flex-start;
}

.message-content {
  max-width: 70%;
  padding: 10px 15px;
  border-radius: 8px;
}

.message.user .message-content {
  background: #409eff;
  color: #fff;
}

.message.assistant .message-content {
  background: #fff;
  border: 1px solid #dcdfe6;
}

.message-role {
  font-size: 12px;
  margin-bottom: 5px;
  opacity: 0.8;
}

.message-text {
  line-height: 1.6;
  white-space: pre-wrap;
}

.chat-input {
  border-top: 1px solid #dcdfe6;
  padding-top: 15px;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 10px;
}

.debug-card {
  margin-top: 20px;
}

.debug-section {
  margin: 15px 0;
}

.memories-list {
  margin-top: 10px;
}

.memory-item {
  margin-bottom: 10px;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
}

.memory-content {
  margin-top: 5px;
  line-height: 1.6;
  color: #606266;
}

.json-display {
  background: #f5f7fa;
  padding: 15px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.5;
}
</style>


