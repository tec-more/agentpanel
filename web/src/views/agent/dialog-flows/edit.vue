<template>
  <div class="dialog-flow-editor">
    <div class="toolbar">
      <span class="flow-name">{{ dialogFlow?.name || '对话流编辑' }}</span>
      <el-tag :type="getStatusType(dialogFlow?.status)" size="small">{{ getStatusName(dialogFlow?.status) }}</el-tag>
      <div class="toolbar-right">
        <el-button @click="handleImportGraph">
          <el-icon><Upload /></el-icon>
          导入
        </el-button>
        <el-button @click="handleExportGraph">
          <el-icon><Download /></el-icon>
          导出
        </el-button>
        <el-button type="primary" @click="saveDialogFlow" :loading="saving">
          <el-icon><Check /></el-icon>
          保存
        </el-button>
        <el-button 
          type="warning" 
          @click="publishDialogFlow" 
          v-if="dialogFlow?.status !== 'active'"
        >
          <el-icon><Check /></el-icon>
          发布
        </el-button>
        <el-button type="success" @click="executeDialog">
          <el-icon><VideoPlay /></el-icon>
          执行
        </el-button>
      </div>
    </div>
    
    <div class="editor-container">
      <div class="node-panel">
        <div class="panel-title">基础节点</div>
        <div 
          v-for="nodeType in nodeCategories.basic" 
          :key="nodeType.type"
          class="node-item"
          draggable="true"
          @dragstart="onDragStart($event, nodeType.type)"
        >
          <el-icon :size="20"><component :is="nodeType.icon" /></el-icon>
          <span>{{ nodeType.label }}</span>
        </div>
        
        <div class="panel-title" style="margin-top: 20px">功能节点</div>
        <div 
          v-for="nodeType in nodeCategories.functions" 
          :key="nodeType.type"
          class="node-item"
          draggable="true"
          @dragstart="onDragStart($event, nodeType.type)"
        >
          <el-icon :size="20"><component :is="nodeType.icon" /></el-icon>
          <span>{{ nodeType.label }}</span>
        </div>
        
        <div class="panel-title" style="margin-top: 20px">内容节点</div>
        <div 
          v-for="nodeType in nodeCategories.content" 
          :key="nodeType.type"
          class="node-item"
          draggable="true"
          @dragstart="onDragStart($event, nodeType.type)"
        >
          <el-icon :size="20"><component :is="nodeType.icon" /></el-icon>
          <span>{{ nodeType.label }}</span>
        </div>
        
        <div class="panel-title" style="margin-top: 20px">操作提示</div>
        <div class="help-text">
          <p>• 拖拽节点到画布创建</p>
          <p>• 点击节点选中并配置</p>
          <p>• 从右侧连接点拖拽到左侧连接点连线</p>
          <p>• 点击连线可删除</p>
        </div>
      </div>
      
      <div class="flow-container" ref="flowContainerRef" @dragover="onDragOver" @drop="onDrop" @mousemove="onMouseMove" @mouseup="onMouseUp" @wheel.prevent="onWheel">
        <div class="canvas-wrapper">
          <div class="canvas" ref="canvasRef" :style="canvasStyle">
            <svg class="edges-svg">
              <defs>
                <marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
                  <polygon points="0 0, 10 3, 0 6" fill="#409eff" />
                </marker>
              </defs>
              <g v-for="edge in edges" :key="edge.id" @click="onEdgeClick(edge)">
                <path
                  :d="getEdgePath(edge)"
                  class="workflow-edge"
                  :class="{ 'selected': selectedEdge?.id === edge.id }"
                  marker-end="url(#arrowhead)"
                />
              </g>
              <path v-if="drawingEdge" :d="tempEdgePath" class="temp-edge" />
            </svg>
            
            <div 
              v-for="node in nodes" 
              :key="node.id"
              class="workflow-node"
              :class="{ 
                'selected': selectedNode?.id === node.id,
                [node.type + '-node']: true 
              }"
              @click="onNodeClick(node)"
              @mousedown="onNodeMouseDown($event, node)"
              :style="{ 
                left: node.position.x + 'px', 
                top: node.position.y + 'px'
              }"
            >
              <div class="connection-point input" 
                   @mousedown.stop="onInputPointMouseDown($event, node)"
                   @mouseup="onInputPointMouseUp($event, node)">
              </div>
              <div class="node-header">
                <span class="node-icon">{{ getNodeIcon(node.type) }}</span>
                <span class="node-label">{{ node.data.label }}</span>
              </div>
              <div class="node-content" v-if="node.data.content || node.data.text || node.data.question || node.data.url">{{ getNodeContent(node) }}</div>
              <div class="connection-point output"
                   @mousedown.stop="onOutputPointMouseDown($event, node)">
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <div class="canvas-zoom-controls">
        <el-button 
          icon="ZoomIn" 
          @click="zoomIn" 
          :disabled="zoom >= MAX_ZOOM"
          size="small"
          circle
          title="放大"
        />
        <div class="canvas-zoom-value">{{ Math.round(zoom * 100) }}%</div>
        <el-button 
          icon="ZoomOut" 
          @click="zoomOut" 
          :disabled="zoom <= MIN_ZOOM"
          size="small"
          circle
          title="缩小"
        />
        <el-button 
          icon="Refresh" 
          @click="resetZoom" 
          size="small"
          circle
          title="重置"
        />
      </div>
      
      <div class="config-panel" v-if="selectedNode || selectedEdge">
        <template v-if="selectedNode">
          <div class="panel-title">节点配置</div>
          <el-form :model="nodeConfig" label-width="80px" size="small">
            <el-form-item label="节点名称">
              <el-input v-model="nodeConfig.label" @change="updateNodeLabel" />
            </el-form-item>
            
            <template v-if="selectedNode.type === 'message'">
              <el-form-item label="消息内容">
                <el-input v-model="nodeConfig.content" type="textarea" :rows="4" @change="updateNodeData" placeholder="输入消息内容，支持变量 {{变量名}}" />
              </el-form-item>
              <el-form-item label="消息类型">
                <el-select v-model="nodeConfig.message_type" @change="updateNodeData" style="width: 100%">
                  <el-option label="普通文本" value="text" />
                  <el-option label="富文本" value="rich_text" />
                  <el-option label="卡片消息" value="card" />
                </el-select>
              </el-form-item>
              <el-form-item label="按钮配置">
                <el-input v-model="nodeConfig.buttons" type="textarea" :rows="2" @change="updateNodeData" placeholder="按钮配置，JSON格式：[{label:按钮1,value:action1}]" />
              </el-form-item>
            </template>
            
            <template v-if="selectedNode.type === 'question'">
              <el-form-item label="问题内容">
                <el-input v-model="nodeConfig.question" type="textarea" :rows="3" @change="updateNodeData" />
              </el-form-item>
              <el-form-item label="变量名">
                <el-input v-model="nodeConfig.variable" @change="updateNodeData" placeholder="存储回答的变量名" />
              </el-form-item>
              <el-form-item label="选项">
                <el-input v-model="nodeConfig.options" type="textarea" :rows="2" @change="updateNodeData" placeholder="选项列表，逗号分隔" />
              </el-form-item>
            </template>
            
            <template v-if="selectedNode.type === 'condition'">
              <el-form-item label="条件表达式">
                <el-input v-model="nodeConfig.condition" type="textarea" :rows="3" @change="updateNodeData" placeholder="如: {{score}} > 60" />
              </el-form-item>
            </template>
            
            <template v-if="selectedNode.type === 'llm'">
              <el-form-item label="选择模型">
                <el-select v-model="nodeConfig.llm_model_id" placeholder="请选择" @change="updateNodeData" style="width: 100%">
                  <el-option v-for="model in models" :key="model.id" :label="`${model.provider_name} - ${model.model_name}`" :value="model.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="提示词">
                <el-input v-model="nodeConfig.llm_prompt" type="textarea" :rows="4" @change="updateNodeData" placeholder="输入提示词，支持变量 {{变量名}}" />
              </el-form-item>
              <el-form-item label="温度">
                <el-slider v-model="nodeConfig.llm_temperature" :min="0" :max="2" :step="0.1" @change="updateNodeData" />
              </el-form-item>
              <el-form-item label="最大Token">
                <el-input-number v-model="nodeConfig.llm_max_tokens" :min="1" :max="4096" @change="updateNodeData" />
              </el-form-item>
              <el-form-item label="流式输出">
                <el-switch v-model="nodeConfig.llm_stream" @change="updateNodeData" active-text="开" inactive-text="关" />
              </el-form-item>
              <el-form-item label="输出变量">
                <el-input v-model="nodeConfig.output_var" @change="updateNodeData" placeholder="存储输出结果的变量名" />
              </el-form-item>
            </template>
            
            <template v-if="selectedNode.type === 'api'">
              <el-form-item label="API URL">
                <el-input v-model="nodeConfig.url" @change="updateNodeData" placeholder="API地址" />
              </el-form-item>
              <el-form-item label="请求方法">
                <el-select v-model="nodeConfig.method" @change="updateNodeData" style="width: 100%">
                  <el-option label="GET" value="GET" />
                  <el-option label="POST" value="POST" />
                  <el-option label="PUT" value="PUT" />
                  <el-option label="DELETE" value="DELETE" />
                </el-select>
              </el-form-item>
              <el-form-item label="请求头">
                <el-input v-model="nodeConfig.headers" type="textarea" :rows="2" @change="updateNodeData" placeholder="JSON格式" />
              </el-form-item>
              <el-form-item label="请求体">
                <el-input v-model="nodeConfig.body" type="textarea" :rows="3" @change="updateNodeData" placeholder="JSON格式" />
              </el-form-item>
            </template>
            
            <template v-if="selectedNode.type === 'tool'">
              <el-form-item label="选择工具">
                <el-select v-model="nodeConfig.tool_name" placeholder="请选择工具" @change="updateNodeData" style="width: 100%">
                  <el-option v-for="tool in tools" :key="tool.name" :label="tool.display_name || tool.name" :value="tool.name">
                    <span style="float: left">{{ tool.display_name || tool.name }}</span>
                    <span style="float: right; color: #8492a6; font-size: 12px">{{ tool.name }}</span>
                  </el-option>
                </el-select>
              </el-form-item>
              <el-form-item label="工具描述" v-if="selectedTool">
                <div style="font-size: 13px; color: #606266; background: #f5f7fa; padding: 8px; border-radius: 4px;">
                  {{ selectedTool.description || '暂无描述' }}
                </div>
              </el-form-item>
              <el-form-item label="工具参数">
                <el-input v-model="nodeConfig.tool_params" type="textarea" :rows="5" @change="updateNodeData" placeholder="JSON格式，支持变量 {{变量名}}" />
              </el-form-item>
              <el-form-item label="输出变量">
                <el-input v-model="nodeConfig.output_var" @change="updateNodeData" placeholder="存储输出结果的变量名，默认 tool_result" />
              </el-form-item>
            </template>
            
            <template v-if="selectedNode.type === 'text'">
              <el-form-item label="文本内容">
                <el-input v-model="nodeConfig.content" type="textarea" :rows="4" @change="updateNodeData" placeholder="输入文本内容，支持变量 {{变量名}}" />
              </el-form-item>
            </template>
            
            <template v-if="selectedNode.type === 'voice'">
              <el-form-item label="语音类型">
                <el-select v-model="nodeConfig.voice_type" @change="updateNodeData" style="width: 100%">
                  <el-option label="文本转语音(TTS)" value="tts" />
                  <el-option label="语音识别(ASR)" value="asr" />
                </el-select>
              </el-form-item>
              <el-form-item label="语言">
                <el-select v-model="nodeConfig.language" @change="updateNodeData" style="width: 100%">
                  <el-option label="中文" value="zh" />
                  <el-option label="英文" value="en" />
                  <el-option label="日文" value="ja" />
                  <el-option label="韩文" value="ko" />
                </el-select>
              </el-form-item>
              <el-form-item label="语音服务商">
                <el-select v-model="nodeConfig.voice_provider_id" @change="updateNodeData" style="width: 100%">
                  <el-option label="请选择" :value="null" />
                  <el-option v-for="provider in voiceProviders" :key="provider.id" :label="provider.name" :value="provider.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="语音文本" v-if="nodeConfig.voice_type === 'tts'">
                <el-input v-model="nodeConfig.text" type="textarea" :rows="3" @change="updateNodeData" placeholder="输入要转换的文本内容，支持变量 {{变量名}}" />
              </el-form-item>
              <el-form-item label="音频URL" v-if="nodeConfig.voice_type === 'asr'">
                <el-input v-model="nodeConfig.audio_url" @change="updateNodeData" placeholder="输入音频文件地址" />
              </el-form-item>
              <el-form-item label="上传音频文件" v-if="nodeConfig.voice_type === 'asr'">
                <el-upload
                  :show-file-list="false"
                  :before-upload="handleAudioUpload"
                  accept="audio/*"
                  class="upload-btn"
                >
                  <el-button type="primary">上传音频</el-button>
                </el-upload>
              </el-form-item>
            </template>
            
            <template v-if="selectedNode.type === 'image'">
              <el-form-item label="图片URL">
                <el-input v-model="nodeConfig.image_url" @change="updateNodeData" placeholder="输入图片地址或点击下方按钮上传" />
              </el-form-item>
              <el-form-item label="上传图片">
                <el-upload
                  :show-file-list="false"
                  :before-upload="handleImageNodeUpload"
                  accept="image/*"
                  class="upload-btn"
                >
                  <el-button type="primary">上传图片</el-button>
                </el-upload>
              </el-form-item>
              <el-form-item label="图片描述">
                <el-input v-model="nodeConfig.image_alt" @change="updateNodeData" placeholder="图片描述（可选），支持变量 {{变量名}}" />
              </el-form-item>
              <el-form-item label="使用大模型分析图片">
                <el-switch v-model="nodeConfig.analyze_image" @change="updateNodeData" active-text="开" inactive-text="关" />
              </el-form-item>
              <el-form-item label="分析提示词" v-if="nodeConfig.analyze_image">
                <el-input v-model="nodeConfig.analysis_prompt" type="textarea" :rows="2" @change="updateNodeData" placeholder="请描述这张图片的内容" />
              </el-form-item>
              <el-form-item label="分析模型" v-if="nodeConfig.analyze_image">
                <el-select v-model="nodeConfig.llm_model_id" placeholder="请选择视觉模型" @change="updateNodeData" style="width: 100%">
                  <el-option v-for="model in models.filter(m => m.supports_vision)" :key="model.id" :label="`${model.provider_name} - ${model.model_name}`" :value="model.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="图片预览">
                <div v-if="nodeConfig.image_url" class="image-preview">
                  <img :src="nodeConfig.image_url" :alt="nodeConfig.image_alt || '图片预览'" />
                </div>
                <div v-else class="image-placeholder">
                  <el-icon class="placeholder-icon"><Picture /></el-icon>
                  <span>暂无图片</span>
                </div>
              </el-form-item>
            </template>
            
            <!-- 知识检索节点配置 -->
            <template v-if="selectedNode.type === 'knowledge_retrieval'">
              <el-form-item label="知识库">
                <el-select v-model="nodeConfig.knowledge_base" @change="updateNodeData" style="width: 100%">
                  <el-option label="默认知识库" value="default" />
                  <el-option label="用户知识库" value="user" />
                </el-select>
              </el-form-item>
              <el-form-item label="检索查询">
                <el-input v-model="nodeConfig.query" type="textarea" :rows="2" @change="updateNodeData" placeholder="检索关键词或语句" />
              </el-form-item>
              <el-form-item label="检索数量">
                <el-input-number v-model="nodeConfig.top_k" :min="1" :max="100" @change="updateNodeData" />
              </el-form-item>
              <el-form-item label="相似度阈值">
                <el-slider v-model="nodeConfig.similarity_threshold" :min="0" :max="1" :step="0.1" @change="updateNodeData" />
              </el-form-item>
              <el-form-item label="输出变量">
                <el-input v-model="nodeConfig.output_var" @change="updateNodeData" placeholder="存储检索结果的变量名" />
              </el-form-item>
            </template>
            
            <!-- 输入节点配置 -->
            <template v-if="selectedNode.type === 'input'">
              <el-form-item label="输入类型">
                <el-checkbox-group v-model="nodeConfig.input_types" @change="updateNodeData">
                  <el-checkbox label="text">文本</el-checkbox>
                  <el-checkbox label="image">图片</el-checkbox>
                  <el-checkbox label="voice">语音</el-checkbox>
                </el-checkbox-group>
              </el-form-item>
              <el-form-item label="输入提示">
                <el-input v-model="nodeConfig.input_placeholder" @change="updateNodeData" placeholder="用户输入提示" />
              </el-form-item>
            </template>
            
            <!-- 输出节点配置 -->
            <template v-if="selectedNode.type === 'output'">
              <el-form-item label="输出类型">
                <el-select v-model="nodeConfig.output_type" @change="updateNodeData" style="width: 100%">
                  <el-option label="文本" value="text" />
                  <el-option label="JSON" value="json" />
                  <el-option label="文件" value="file" />
                </el-select>
              </el-form-item>
              <el-form-item label="输出内容">
                <el-input v-model="nodeConfig.output_content" type="textarea" :rows="4" @change="updateNodeData" placeholder="输出内容或变量表达式" />
              </el-form-item>
              <el-form-item label="输出变量">
                <el-input v-model="nodeConfig.output_var" @change="updateNodeData" placeholder="存储输出结果的变量名" />
              </el-form-item>
            </template>
            
          </el-form>
          
          <el-button type="danger" size="small" @click="deleteSelectedNode" style="width: 100%; margin-top: 10px;">
            删除节点
          </el-button>
        </template>
        
        <template v-if="selectedEdge">
          <div class="panel-title">连线配置</div>
          <div class="edge-info">
            <p><strong>源节点：</strong>{{ getNodeById(selectedEdge.source)?.data.label }}</p>
            <p><strong>目标节点：</strong>{{ getNodeById(selectedEdge.target)?.data.label }}</p>
          </div>
          <el-divider content-position="left">属性配置</el-divider>
          <el-form-item label="启用">
            <el-switch v-model="selectedEdge.enabled" @change="updateEdgeData" />
          </el-form-item>
          <el-form-item label="优先级">
            <el-input-number v-model="selectedEdge.priority" :min="0" :max="100" @change="updateEdgeData" />
          </el-form-item>
          <el-form-item label="条件表达式">
            <el-input v-model="selectedEdge.condition" type="textarea" :rows="2" @change="updateEdgeData" placeholder="如: {{params.budget}} > 5000" />
          </el-form-item>
          <el-form-item label="条件描述">
            <el-input v-model="selectedEdge.description" @change="updateEdgeData" placeholder="条件的简要描述" />
          </el-form-item>
          <el-button type="danger" size="small" @click="deleteSelectedEdge" style="width: 100%">
            删除连线
          </el-button>
        </template>
      </div>
    </div>

    <el-dialog v-model="executeDialogVisible" title="执行对话流" width="900px" class="wechat-style-dialog">
      <div class="chat-container">
        <!-- 聊天历史 -->
        <div class="chat-messages">
          <div
            v-for="(msg, index) in dialogHistory"
            :key="index"
            :class="['message', msg.role, { 'message-streaming': msg.role === 'assistant' && msg.isStreaming }]"
          >
            <div class="message-avatar">{{ msg.role === 'user' ? '👤' : '🤖' }}</div>
            <div class="message-content-wrapper">
              <div class="message-role">{{ msg.role === 'user' ? '用户' : 'AI' }}</div>
              <div v-if="msg.images && msg.images.length > 0" class="message-images">
                <img
                  v-for="(img, imgIdx) in msg.images"
                  :key="imgIdx"
                  :src="img"
                  class="msg-image"
                />
              </div>
              <div v-if="msg.audioUrl" class="message-audio">
                <audio :src="msg.audioUrl" controls class="audio-player">
                  您的浏览器不支持音频播放
                </audio>
              </div>
              <div class="message-content">{{ msg.content }}</div>
              <div class="message-time">{{ msg.time }}</div>
              
              <!-- AI的思考、行动、观察、结果 - 可折叠 -->
              <div v-if="msg.role === 'assistant' && msg.process && msg.process.length > 0" class="message-process">
                <div
                  v-for="(process, pIndex) in msg.process"
                  :key="pIndex"
                  :class="['process-item', process.type, { collapsed: process.collapsed }]"
                >
                  <div class="process-header" @click="process.collapsed = !process.collapsed">
                    <span class="process-label">{{ process.label }}</span>
                    <span class="process-time">{{ process.time }}</span>
                    <span class="collapse-icon">{{ process.collapsed ? '▶' : '▼' }}</span>
                  </div>
                  <div class="process-content" v-show="!process.collapsed">{{ process.content }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="chat-input-area">
          <div v-if="uploadedImages.length > 0" class="image-preview-list">
            <div v-for="(img, idx) in uploadedImages" :key="idx" class="image-preview-item">
              <img :src="img.url" class="preview-thumb" />
              <el-icon class="remove-image" @click="removeImage(idx)"><Close /></el-icon>
            </div>
          </div>
          <div v-if="uploadedAudio.length > 0" class="audio-preview-list">
            <div v-for="(audio, idx) in uploadedAudio" :key="idx" class="audio-preview-item">
              <audio :src="audio.url" controls class="audio-preview-player" />
              <el-icon class="remove-audio" @click="removeAudio(idx)"><Close /></el-icon>
            </div>
          </div>
          <el-input
            v-if="inputTypes.includes('text')"
            v-model="currentInput"
            type="textarea"
            :rows="3"
            :placeholder="inputPlaceholder || '请输入你要说的话...'"
            @keyup.enter.ctrl="doExecute"
            @paste="handlePaste"
            class="input-textarea"
          />
          <div class="input-actions">
            <el-upload
              v-if="inputTypes.includes('image')"
              :show-file-list="false"
              :before-upload="beforeImageUpload"
              accept="image/*"
              multiple
              class="upload-btn"
            >
              <el-button>
                <el-icon><Picture /></el-icon>
                图片
              </el-button>
            </el-upload>
            <el-button v-if="inputTypes.includes('voice')" @click="toggleVoiceRecording">
              <el-icon><Mic /></el-icon>
              {{ recording ? '停止录音' : '语音' }}
            </el-button>
            <el-button @click="clearDialogHistory" :disabled="dialogHistory.length === 0">清空历史</el-button>
            <el-button @click="executeDialogVisible = false">关闭</el-button>
            <el-button type="primary" @click="doExecute" :loading="executing">发送</el-button>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { 
  ArrowLeft, Check, VideoPlay, ChatDotRound, QuestionFilled, 
  Share, User, Connection, VideoPlay as Play, CircleCheck, 
  Document, Mic, Upload, Download, Picture, Cpu, Close
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getDialogFlow, updateDialogFlow, executeDialogFlow, executeDialogFlowAuto, getActiveTools } from '@/api/agent'
import { getAgents } from '@/api/agent'
import { getModelList, getProviderList } from '@/api/llm'
import { getEdgePathByType, getDefaultEdgeType } from '@/utils/edge-renderer'
import { ZoomIn, ZoomOut, Refresh } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const flowId = route.params.id
const dialogFlow = ref(null)
const saving = ref(false)
const agents = ref([])
const models = ref([])
const voiceProviders = ref([])
const tools = ref([])

const nodes = ref([])
const edges = ref([])
const selectedNode = ref(null)
const selectedEdge = ref(null)

const nodeConfig = reactive({
  label: '',
  content: '',
  text: '',
  image_url: '',
  image_alt: '',
  image_analysis: '',
  analyze_image: false,
  analysis_prompt: '',
  voice_type: 'tts',
  voice_provider_id: null,
  language: 'zh',
  audio_url: '',
  message_type: 'text',
  buttons: '',
  question: '',
  variable: '',
  options: '',
  condition: '',
  agent_id: null,
  input_variable: '',
  url: '',
  method: 'GET',
  headers: '{}',
  body: '{}',
  // 输入节点配置
  input_types: ['text'],
  input_placeholder: '',
  // 知识检索节点配置
  knowledge_base: 'default',
  query: '',
  top_k: 5,
  similarity_threshold: 0.7,
  // 输出节点配置
  output_type: 'text',
  output_content: '',
  output_var: '',
  // 大模型节点配置
  llm_model_id: null,
  llm_prompt: '',
  llm_temperature: 0.7,
  llm_max_tokens: 1024,
  llm_stream: false,
  // 工具节点配置
  tool_name: '',
  tool_params: '{}'
})

const nodeCategories = {
  basic: [
    { type: 'start', label: '开始', icon: Play, next: ['input', 'message', 'text', 'image', 'voice', 'llm', 'api', 'knowledge_retrieval', 'tool'] },
    { type: 'end', label: '结束', icon: CircleCheck, next: [] },
    { type: 'input', label: '输入', icon: Document, next: ['message', 'text', 'image', 'voice', 'llm', 'api', 'knowledge_retrieval', 'tool'] },
    { type: 'output', label: '输出', icon: Share, next: ['end'] }
  ],
  functions: [
    { type: 'llm', label: '大模型', icon: Cpu, next: ['message', 'text', 'image', 'voice', 'api', 'knowledge_retrieval', 'tool', 'output'] },
    { type: 'knowledge_retrieval', label: '知识检索', icon: Document, next: ['message', 'text', 'image', 'voice', 'llm', 'api', 'tool', 'output'] },
    { type: 'api', label: 'API调用', icon: Connection, next: ['message', 'text', 'image', 'voice', 'llm', 'knowledge_retrieval', 'tool', 'output'] },
    { type: 'tool', label: '工具', icon: User, next: ['message', 'text', 'image', 'voice', 'llm', 'api', 'knowledge_retrieval', 'output'] }
  ],
  content: [
    { type: 'message', label: '消息', icon: ChatDotRound, next: ['text', 'image', 'voice', 'llm', 'api', 'knowledge_retrieval', 'output'] },
    { type: 'text', label: '文本', icon: Document, next: ['message', 'image', 'voice', 'llm', 'api', 'knowledge_retrieval', 'output'] },
    { type: 'image', label: '图片', icon: Picture, next: ['message', 'text', 'voice', 'llm', 'api', 'knowledge_retrieval', 'output'] },
    { type: 'voice', label: '语音', icon: Mic, next: ['message', 'text', 'image', 'llm', 'api', 'knowledge_retrieval', 'output'] }
  ]
}

const allNodeTypes = [
  ...nodeCategories.basic,
  ...nodeCategories.functions,
  ...nodeCategories.content
]

const executeDialogVisible = ref(false)
const executing = ref(false)
const executeInput = ref('')
const executeResult = ref('')
const dialogHistory = ref([])
const currentInput = ref('')
const latestResponse = ref('')
const uploadedImages = ref([])
const uploadedAudio = ref([])
const inputTypes = ref(['text'])
const inputPlaceholder = ref('')
const recording = ref(false)
let mediaRecorder = null
let audioChunks = []

const drawingEdge = ref(false)
const edgeStartNode = ref(null)
const edgeStartPoint = ref({ x: 0, y: 0 })
const currentMousePos = ref({ x: 0, y: 0 })

const draggingNode = ref(null)
const dragOffset = ref({ x: 0, y: 0 })

const zoom = ref(1)
const MIN_ZOOM = 0.2
const MAX_ZOOM = 3
const ZOOM_STEP = 0.1

const canvasRef = ref(null)
const flowContainerRef = ref(null)

const canvasStyle = computed(() => {
  return {
    transform: `scale(${zoom.value})`,
    transformOrigin: 'top left'
  };
});

const zoomIn = () => {
  if (zoom.value < MAX_ZOOM) {
    zoom.value = Math.min(zoom.value + ZOOM_STEP, MAX_ZOOM)
  }
}

const zoomOut = () => {
  if (zoom.value > MIN_ZOOM) {
    zoom.value = Math.max(zoom.value - ZOOM_STEP, MIN_ZOOM)
  }
}

const resetZoom = () => {
  zoom.value = 1
}

const onWheel = (event) => {
  event.preventDefault()
  const delta = event.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP
  zoom.value = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, zoom.value + delta))
}

const tempEdgePath = computed(() => {
  if (!drawingEdge.value) return ''
  const startX = edgeStartPoint.value.x
  const startY = edgeStartPoint.value.y
  const endX = currentMousePos.value.x
  const endY = currentMousePos.value.y
  return getEdgePathByType(edgeType, startX, startY, endX, endY, 0)
})

const statusMap = { draft: '草稿', active: '启用', inactive: '禁用' }
const getStatusName = (status) => statusMap[status] || status
const getStatusType = (status) => {
  const map = { draft: 'info', active: 'success', inactive: 'danger' }
  return map[status] || ''
}

const getNodeIcon = (type) => {
  const icons = {
    start: '▶️',
    end: '⏹️',
    input: '📥',
    output: '📤',
    message: '💬',
    text: '📝',
    image: '🖼️',
    voice: '🎤',
    question: '❓',
    condition: '🔀',
    agent: '🤖',
    llm: '🧠',
    api: '🔗',
    knowledge_retrieval: '📚'
  }
  return icons[type] || '📦'
}

const getNodeContent = (node) => {
  if (node.data.content) return node.data.content
  if (node.data.text) return node.data.text
  if (node.data.question) return node.data.question
  if (node.data.url) return node.data.url
  return ''
}

const getNodeById = (id) => {
  return nodes.value.find(n => n.id === id)
}

// 使用全局配置的连线类型
const edgeType = getDefaultEdgeType()

const getEdgePath = (edge) => {
  const sourceNode = getNodeById(edge.source)
  const targetNode = getNodeById(edge.target)
  
  if (!sourceNode || !targetNode) return ''
  
  const sourceX = sourceNode.position.x + 150
  const sourceY = sourceNode.position.y + 20
  const targetX = targetNode.position.x
  const targetY = targetNode.position.y + 20
  
  // 计算同一源节点和目标节点的连线索引，用于双向偏移
  const sourceEdges = nodes.value ? edges.value.filter(e => e.source === edge.source) : []
  const targetEdges = nodes.value ? edges.value.filter(e => e.target === edge.target) : []
  const edgeIndex = sourceEdges.findIndex(e => e.id === edge.id)
  const targetEdgeIndex = targetEdges.findIndex(e => e.id === edge.id)
  const totalEdgesFromSource = sourceEdges.length
  const totalEdgesToTarget = targetEdges.length
  
  // 计算垂直偏移量，避免重叠
  let totalOffset = 0
  if (totalEdgesFromSource > 1 || totalEdgesToTarget > 1) {
    const spacing = 30
    const avgIndex = (edgeIndex + targetEdgeIndex) / 2
    const maxCount = Math.max(totalEdgesFromSource, totalEdgesToTarget)
    const totalHeight = (maxCount - 1) * spacing
    const startOffset = -totalHeight / 2
    totalOffset = startOffset + avgIndex * spacing
  }
  
  return getEdgePathByType(edgeType, sourceX, sourceY, targetX, targetY, totalOffset)
}

const goBack = () => {
  router.push('/panel/agent/dialog-flows')
}

const fetchDialogFlow = async () => {
  try {
    const res = await getDialogFlow(flowId)
    dialogFlow.value = res.data
    if (res.data.flow_data) {
      nodes.value = res.data.flow_data.nodes || []
      edges.value = (res.data.flow_data.edges || []).map(edge => ({
        ...edge,
        enabled: edge.enabled !== false,
        priority: edge.priority || 0,
        condition: edge.condition || '',
        description: edge.description || ''
      }))
    } else if (res.data.definition) {
      nodes.value = res.data.definition.nodes || []
      edges.value = (res.data.definition.edges || []).map(edge => ({
        ...edge,
        enabled: edge.enabled !== false,
        priority: edge.priority || 0,
        condition: edge.condition || '',
        description: edge.description || ''
      }))
    }
  } catch (error) {
    ElMessage.error('获取对话流失败')
    console.error(error)
  }
}

const fetchAgents = async () => {
  try {
    const res = await getAgents({ limit: 1000 })
    agents.value = res.data?.items || res.data || []
  } catch (error) {
    console.error(error)
  }
}

const fetchModels = async () => {
  try {
    const res = await getModelList({ limit: 1000 })
    models.value = res.data?.items || res.data || []
  } catch (error) {
    console.error(error)
  }
}

const fetchVoiceProviders = async () => {
  try {
    const res = await getProviderList({ limit: 100 })
    voiceProviders.value = res.data?.items || res.data || []
  } catch (error) {
    console.error(error)
  }
}

const fetchTools = async () => {
  try {
    const res = await getActiveTools()
    tools.value = res.data || []
  } catch (error) {
    console.error('获取工具列表失败:', error)
  }
}

const selectedTool = computed(() => {
  return tools.value.find(t => t.name === nodeConfig.tool_name) || null
})

const handleImageNodeUpload = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  try {
    const response = await fetch('/api/v1/upload/image', {
      method: 'POST',
      body: formData
    })
    const result = await response.json()
    if (result.success && result.data && result.data.url) {
      const rawUrl = result.data.url
      let imageUrl = ''
      if (rawUrl.startsWith('http')) {
        imageUrl = rawUrl
      } else if (rawUrl.startsWith('/uploads/images/')) {
        const parts = rawUrl.replace('/uploads/images/', '').split('/')
        if (parts.length >= 4) {
          imageUrl = `/api/v1/upload/images/${parts[0]}/${parts[1]}/${parts[2]}/${parts.slice(3).join('/')}`
        } else {
          imageUrl = window.location.origin + rawUrl
        }
      } else {
        imageUrl = window.location.origin + rawUrl
      }
      nodeConfig.image_url = imageUrl
      updateNodeData()
      ElMessage.success('图片上传成功')
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('图片上传失败')
  }
  return false
}

const handleAudioUpload = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  try {
    const response = await fetch('/api/v1/upload/audio', {
      method: 'POST',
      body: formData
    })
    const result = await response.json()
    if (result.success && result.data && result.data.url) {
      nodeConfig.audio_url = result.data.url
      updateNodeData()
      ElMessage.success('音频上传成功')
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('音频上传失败')
  }
  return false
}

const saveDialogFlow = async () => {
  saving.value = true
  try {
    await updateDialogFlow(flowId, {
      flow_data: { nodes: nodes.value, edges: edges.value }
    })
    ElMessage.success('保存成功')
  } catch (error) {
    ElMessage.error('保存失败')
    console.error(error)
  } finally {
    saving.value = false
  }
}

const publishDialogFlow = async () => {
  saving.value = true
  try {
    await updateDialogFlow(flowId, {
      status: 'active',
      flow_data: { nodes: nodes.value, edges: edges.value }
    })
    dialogFlow.value.status = 'active'
    ElMessage.success('发布成功')
  } catch (error) {
    ElMessage.error('发布失败')
    console.error(error)
  } finally {
    saving.value = false
  }
}

const onDragStart = (event, nodeType) => {
  event.dataTransfer.setData('nodeType', nodeType)
  event.dataTransfer.effectAllowed = 'move'
}

const onDragOver = (event) => {
  event.preventDefault()
  event.dataTransfer.dropEffect = 'move'
}

const onDrop = (event) => {
  const type = event.dataTransfer.getData('nodeType')
  if (!type) return
  
  const canvas = event.currentTarget
  const rect = canvas.getBoundingClientRect()
  const position = {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top
  }
  
  const newNode = {
    id: `${type}-${Date.now()}`,
    type,
    position,
    data: { label: allNodeTypes.find(n => n.type === type)?.label || type }
  }
  nodes.value.push(newNode)
}

const onNodeClick = (node) => {
  selectedEdge.value = null
  selectedNode.value = node
  nodeConfig.label = node.data.label || ''
  nodeConfig.content = node.data.content || ''
  nodeConfig.text = node.data.text || ''
  nodeConfig.image_url = node.data.image_url || ''
  nodeConfig.image_alt = node.data.image_alt || ''
  nodeConfig.voice_type = node.data.voice_type || 'tts'
  nodeConfig.language = node.data.language || 'zh-CN'
  nodeConfig.question = node.data.question || ''
  nodeConfig.variable = node.data.variable || ''
  nodeConfig.options = node.data.options || ''
  nodeConfig.condition = node.data.condition || ''
  nodeConfig.agent_id = node.data.agent_id || null
  nodeConfig.input_variable = node.data.input_variable || ''
  nodeConfig.url = node.data.url || ''
  nodeConfig.method = node.data.method || 'GET'
  nodeConfig.headers = node.data.headers || '{}'
  nodeConfig.body = node.data.body || '{}'
  nodeConfig.input_types = node.data.input_types || ['text']
  nodeConfig.input_placeholder = node.data.input_placeholder || ''
  nodeConfig.knowledge_base = node.data.knowledge_base || 'default'
  nodeConfig.query = node.data.query || ''
  nodeConfig.top_k = node.data.top_k || 5
  nodeConfig.similarity_threshold = node.data.similarity_threshold || 0.7
  nodeConfig.output_var = node.data.output_var || ''
  nodeConfig.output_type = node.data.output_type || 'text'
  nodeConfig.output_content = node.data.output_content || ''
  nodeConfig.llm_model_id = node.data.llm_model_id || null
  nodeConfig.llm_prompt = node.data.llm_prompt || ''
  nodeConfig.llm_temperature = node.data.llm_temperature || 0.7
  nodeConfig.llm_max_tokens = node.data.llm_max_tokens || 1024
  nodeConfig.llm_stream = node.data.llm_stream || false
  nodeConfig.tool_name = node.data.tool_name || ''
  nodeConfig.tool_params = node.data.tool_params || '{}'
}

const onNodeMouseDown = (event, node) => {
  if (event.target.classList.contains('connection-point')) return
  
  draggingNode.value = node
  const canvas = event.currentTarget.closest('.canvas')
  const rect = canvas.getBoundingClientRect()
  dragOffset.value = {
    x: event.clientX - rect.left - node.position.x,
    y: event.clientY - rect.top - node.position.y
  }
  event.preventDefault()
}

const onEdgeClick = (edge) => {
  selectedNode.value = null
  selectedEdge.value = edge
}

const onOutputPointMouseDown = (event, node) => {
  drawingEdge.value = true
  edgeStartNode.value = node
  edgeStartPoint.value = {
    x: node.position.x + 150,
    y: node.position.y + 20
  }
  currentMousePos.value = { ...edgeStartPoint.value }
}

const onInputPointMouseUp = (event, node) => {
  if (drawingEdge.value && edgeStartNode.value && edgeStartNode.value.id !== node.id) {
    const exists = edges.value.find(e => 
      e.source === edgeStartNode.value.id && e.target === node.id
    )
    
    if (!exists) {
      const newEdge = {
        id: `edge-${Date.now()}`,
        source: edgeStartNode.value.id,
        target: node.id,
        enabled: true,
        priority: 0,
        condition: '',
        description: ''
      }
      edges.value.push(newEdge)
      ElMessage.success('连线创建成功')
    } else {
      ElMessage.warning('连线已存在')
    }
  }
  
  drawingEdge.value = false
  edgeStartNode.value = null
}

const onMouseMove = (event) => {
  if (drawingEdge.value) {
    const canvas = event.currentTarget
    const rect = canvas.getBoundingClientRect()
    currentMousePos.value = {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top
    }
  }
  
  if (draggingNode.value) {
    const canvas = event.currentTarget
    const rect = canvas.getBoundingClientRect()
    draggingNode.value.position = {
      x: event.clientX - rect.left - dragOffset.value.x,
      y: event.clientY - rect.top - dragOffset.value.y
    }
  }
}

const onMouseUp = () => {
  drawingEdge.value = false
  edgeStartNode.value = null
  draggingNode.value = null
}

const updateNodeLabel = () => {
  if (selectedNode.value) {
    selectedNode.value.data.label = nodeConfig.label
  }
}

const updateNodeData = () => {
  if (selectedNode.value) {
    selectedNode.value.data = {
      ...selectedNode.value.data,
      label: nodeConfig.label,
      content: nodeConfig.content,
      text: nodeConfig.text,
      image_url: nodeConfig.image_url,
      image_alt: nodeConfig.image_alt,
      voice_type: nodeConfig.voice_type,
      language: nodeConfig.language,
      question: nodeConfig.question,
      variable: nodeConfig.variable,
      options: nodeConfig.options,
      condition: nodeConfig.condition,
      agent_id: nodeConfig.agent_id,
      input_variable: nodeConfig.input_variable,
      url: nodeConfig.url,
      method: nodeConfig.method,
      headers: nodeConfig.headers,
      body: nodeConfig.body,
      input_types: nodeConfig.input_types,
      input_placeholder: nodeConfig.input_placeholder,
      knowledge_base: nodeConfig.knowledge_base,
      query: nodeConfig.query,
      top_k: nodeConfig.top_k,
      similarity_threshold: nodeConfig.similarity_threshold,
      output_var: nodeConfig.output_var,
      output_type: nodeConfig.output_type,
      output_content: nodeConfig.output_content,
      llm_model_id: nodeConfig.llm_model_id,
      llm_prompt: nodeConfig.llm_prompt,
      llm_temperature: nodeConfig.llm_temperature,
      llm_max_tokens: nodeConfig.llm_max_tokens,
      llm_stream: nodeConfig.llm_stream,
      tool_name: nodeConfig.tool_name,
      tool_params: nodeConfig.tool_params
    }
  }
}

const deleteSelectedNode = () => {
  if (selectedNode.value) {
    edges.value = edges.value.filter(e => 
      e.source !== selectedNode.value.id && e.target !== selectedNode.value.id
    )
    
    const index = nodes.value.findIndex(n => n.id === selectedNode.value.id)
    if (index > -1) {
      nodes.value.splice(index, 1)
    }
    selectedNode.value = null
    ElMessage.success('节点已删除')
  }
}

const deleteSelectedEdge = () => {
  if (selectedEdge.value) {
    const index = edges.value.findIndex(e => e.id === selectedEdge.value.id)
    if (index > -1) {
      edges.value.splice(index, 1)
    }
    selectedEdge.value = null
    ElMessage.success('连线已删除')
  }
}

const updateEdgeData = () => {
  if (selectedEdge.value) {
    selectedEdge.value.enabled = selectedEdge.value.enabled !== false
    selectedEdge.value.priority = selectedEdge.value.priority || 0
    console.log('边的属性已更新:', selectedEdge.value)
  }
}

const executeDialog = () => {
  executeInput.value = ''
  executeResult.value = ''
  // 清空之前的输入和回复，但保留对话历史
  currentInput.value = ''
  latestResponse.value = ''
  uploadedImages.value = []
  
  // 从输入节点读取配置
  const inputNode = nodes.value.find(n => n.type === 'input')
  if (inputNode && inputNode.data) {
    inputTypes.value = inputNode.data.input_types || ['text']
    inputPlaceholder.value = inputNode.data.input_placeholder || ''
  } else {
    inputTypes.value = ['text']
    inputPlaceholder.value = ''
  }
  
  executeDialogVisible.value = true
}

const clearDialogHistory = () => {
  dialogHistory.value = []
  currentInput.value = ''
  latestResponse.value = ''
  uploadedImages.value = []
  ElMessage.success('对话历史已清空')
}

const beforeImageUpload = async (file) => {
  const isImage = file.type.startsWith('image/')
  if (!isImage) {
    ElMessage.error('只能上传图片文件!')
    return false
  }
  const isLt10M = file.size / 1024 / 1024 < 10
  if (!isLt10M) {
    ElMessage.error('图片大小不能超过 10MB!')
    return false
  }
  
  try {
    const formData = new FormData()
    formData.append('file', file)
    
    const token = localStorage.getItem('token')
    const headers = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    
    const response = await fetch('/api/v1/upload/image', {
      method: 'POST',
      headers: headers,
      body: formData
    })
    
    if (!response.ok) {
      const errorText = await response.text()
      ElMessage.error(`上传失败: ${response.status} ${errorText}`)
      return false
    }
    
    const result = await response.json()
    if (result.success && result.data && result.data.url) {
      const rawUrl = result.data.url
      let imageUrl = ''
      if (rawUrl.startsWith('http')) {
        imageUrl = rawUrl
      } else if (rawUrl.startsWith('/uploads/images/')) {
        const parts = rawUrl.replace('/uploads/images/', '').split('/')
        if (parts.length >= 4) {
          imageUrl = `/api/v1/upload/images/${parts[0]}/${parts[1]}/${parts[2]}/${parts.slice(3).join('/')}`
        } else {
          imageUrl = window.location.origin + rawUrl
        }
      } else {
        imageUrl = window.location.origin + rawUrl
      }
      uploadedImages.value.push({
        url: imageUrl,
        name: file.name
      })
      ElMessage.success('图片上传成功')
    } else {
      ElMessage.error(result.message || '上传失败')
    }
  } catch (error) {
    ElMessage.error('上传失败: ' + error.message)
    console.error('图片上传错误:', error)
  }
  
  return false
}

const removeImage = (index) => {
  uploadedImages.value.splice(index, 1)
}

const removeAudio = (index) => {
  uploadedAudio.value.splice(index, 1)
}

const toggleVoiceRecording = async () => {
  if (recording.value) {
    stopRecording()
  } else {
    await startRecording()
  }
}

const startRecording = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaRecorder = new MediaRecorder(stream)
    audioChunks = []
    
    mediaRecorder.ondataavailable = (event) => {
      audioChunks.push(event.data)
    }
    
    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' })
      const audioFile = new File([audioBlob], `recording-${Date.now()}.webm`, { type: 'audio/webm' })
      
      try {
        const formData = new FormData()
        formData.append('file', audioFile)
        
        const token = localStorage.getItem('token')
        const headers = {}
        if (token) {
          headers['Authorization'] = `Bearer ${token}`
        }
        
        const response = await fetch('/api/v1/upload/audio', {
          method: 'POST',
          headers: headers,
          body: formData
        })
        
        if (!response.ok) {
          throw new Error(`上传失败: ${response.status}`)
        }
        
        const result = await response.json()
        if (result.success && result.data && result.data.url) {
          if (!uploadedAudio.value) {
            uploadedAudio.value = []
          }
          uploadedAudio.value.push({
            url: result.data.url,
            name: audioFile.name
          })
          ElMessage.success('音频上传成功')
        }
      } catch (error) {
        ElMessage.error('音频上传失败: ' + error.message)
        console.error('音频上传错误:', error)
      }
      
      stream.getTracks().forEach(track => track.stop())
    }
    
    mediaRecorder.start()
    recording.value = true
    ElMessage.info('开始录音...')
  } catch (error) {
    ElMessage.error('无法访问麦克风: ' + error.message)
    console.error('录音错误:', error)
  }
}

const stopRecording = () => {
  if (mediaRecorder && recording.value) {
    mediaRecorder.stop()
    recording.value = false
    ElMessage.success('录音结束')
  }
}

const handlePaste = async (event) => {
  const items = event.clipboardData?.items
  if (!items) {
    ElMessage.warning('浏览器不支持剪贴板操作')
    return
  }
  
  let hasImage = false
  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    if (item.type.startsWith('image/')) {
      hasImage = true
      event.preventDefault()
      const file = item.getAsFile()
      if (file) {
        if (!file.name || file.name === 'blob') {
          const ext = item.type.split('/')[1] || 'png'
          file.name = `clipboard-image-${Date.now()}.${ext}`
        }
        await beforeImageUpload(file)
      } else {
        ElMessage.error('无法从剪贴板获取图片')
      }
      break
    }
  }
  
  if (!hasImage) {
    return
  }
}

const doExecute = async () => {
  if (!currentInput.value.trim() && uploadedImages.value.length === 0 && uploadedAudio.value.length === 0) {
    ElMessage.warning('请输入内容或上传图片/语音')
    return
  }
  
  executing.value = true
  try {
    const userContent = currentInput.value || '请描述这张图片'
    const userMessage = {
      role: 'user',
      content: userContent,
      images: uploadedImages.value.map(img => img.url),
      audio: uploadedAudio.value.map(a => a.url),
      time: new Date().toLocaleTimeString('zh-CN')
    }
    dialogHistory.value.push(userMessage)
    
    const input = {
      text: userContent,
      image_urls: uploadedImages.value.map(img => img.url),
      audio_urls: uploadedAudio.value.map(a => a.url),
      history: [...dialogHistory.value]
    }
    
    uploadedImages.value = []
    uploadedAudio.value = []
    
    const msgIndex = dialogHistory.value.length
    dialogHistory.value.push({
      role: 'assistant',
      content: '',
      time: new Date().toLocaleTimeString('zh-CN'),
      isStreaming: true
    })
    
    const getAssistantMsg = () => dialogHistory.value[msgIndex]
    const setAssistantContent = (content) => {
      dialogHistory.value[msgIndex].content = content
      latestResponse.value = content
    }
    const appendAssistantContent = (content) => {
      dialogHistory.value[msgIndex].content += content
      latestResponse.value = dialogHistory.value[msgIndex].content
    }
    const setAssistantStreaming = (streaming) => {
      dialogHistory.value[msgIndex].isStreaming = streaming
    }
    
    const executionResults = []
    
    executeDialogFlowAuto(flowId, input, {
      onStart: () => {
        console.log('对话流执行开始')
      },
      onData: (data) => {
        executionResults.push(data)
        
        if (data.type === 'stream') {
          if (data.full_content !== undefined) {
            setAssistantContent(data.full_content)
          }
        } else if (data.type === 'message') {
          if (data.content) {
            appendAssistantContent(data.content + '\n')
          }
        } else if (data.type === 'llm_complete') {
          if (data.content) {
            appendAssistantContent(data.content + '\n')
          }
        } else if (data.type === 'knowledge_result') {
          if (data.results) {
            const contexts = data.results.map(r => r.content).join('\n')
            appendAssistantContent(`[知识检索结果]\n${contexts}\n`)
          }
        } else if (data.type === 'api_result') {
          if (data.result) {
            appendAssistantContent(`[API响应]\n${JSON.stringify(data.result, null, 2)}\n`)
          }
        } else if (data.type === 'image') {
          if (data.image_url) {
            appendAssistantContent(`[图片]\n${data.image_url}\n`)
            const msgIndex = dialogHistory.value.length - 1
            if (msgIndex >= 0 && dialogHistory.value[msgIndex].role === 'assistant') {
              if (!dialogHistory.value[msgIndex].images) {
                dialogHistory.value[msgIndex].images = []
              }
              dialogHistory.value[msgIndex].images.push(data.image_url)
            }
          }
        } else if (data.type === 'image_analysis') {
          if (data.analysis) {
            appendAssistantContent(`[图片分析]\n${data.analysis}\n`)
          }
        } else if (data.type === 'voice') {
          if (data.audio_url) {
            appendAssistantContent(`[语音消息]\n${data.audio_url}\n`)
            const msgIndex = dialogHistory.value.length - 1
            if (msgIndex >= 0 && dialogHistory.value[msgIndex].role === 'assistant') {
              dialogHistory.value[msgIndex].audioUrl = data.audio_url
            }
          } else if (data.recognized_text) {
            appendAssistantContent(`[语音识别]\n${data.recognized_text}\n`)
          }
        } else if (data.type === 'voice_tts') {
          if (data.audio_url) {
            appendAssistantContent(`[TTS语音]\n${data.audio_url}\n`)
            const msgIndex = dialogHistory.value.length - 1
            if (msgIndex >= 0 && dialogHistory.value[msgIndex].role === 'assistant') {
              dialogHistory.value[msgIndex].audioUrl = data.audio_url
            }
          }
        } else if (data.type === 'voice_asr') {
          if (data.recognized_text) {
            appendAssistantContent(`[ASR识别]\n${data.recognized_text}\n`)
          }
        } else if (data.type === 'complete') {
          setAssistantStreaming(false)
        } else if (data.type === 'error') {
          setAssistantStreaming(false)
          setAssistantContent('执行失败: ' + (data.message || '未知错误'))
        }
      },
      onComplete: () => {
        setAssistantStreaming(false)
        currentInput.value = ''
        executeResult.value = JSON.stringify(executionResults, null, 2)
        ElMessage.success('执行完成')
        executing.value = false
      },
      onError: (error) => {
        setAssistantStreaming(false)
        setAssistantContent('执行失败: ' + (error.message || '未知错误'))
        executeResult.value = error.message || '执行失败'
        ElMessage.error('执行失败')
        executing.value = false
      }
    })
  } catch (error) {
    const errorMessage = {
      role: 'assistant',
      content: '执行失败: ' + (error.message || '未知错误'),
      time: new Date().toLocaleTimeString('zh-CN')
    }
    dialogHistory.value.push(errorMessage)
    latestResponse.value = errorMessage.content
    executeResult.value = error.message || '执行失败'
    ElMessage.error('执行失败')
    executing.value = false
  }
}

const handleExportGraph = () => {
  const graphData = {
    nodes: nodes.value,
    edges: edges.value,
    name: dialogFlow.value?.name || 'dialog-flow',
    description: dialogFlow.value?.description || ''
  }
  const blob = new Blob([JSON.stringify(graphData, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${dialogFlow.value?.name || 'dialog-flow'}-${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('图结构导出成功')
}

const handleImportGraph = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = (e) => {
    const file = e.target.files[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (event) => {
        try {
          const data = JSON.parse(event.target.result)
          if (data.nodes && data.edges) {
            nodes.value = data.nodes
            edges.value = data.edges
            ElMessage.success('图结构导入成功')
          } else {
            ElMessage.error('文件格式错误，缺少nodes或edges字段')
          }
        } catch (error) {
          ElMessage.error('导入失败：文件格式错误')
          console.error(error)
        }
      }
      reader.readAsText(file)
    }
  }
  input.click()
}

onMounted(() => {
  fetchDialogFlow()
  fetchAgents()
  fetchModels()
  fetchVoiceProviders()
  fetchTools()
})
</script>

<style scoped>
.dialog-flow-editor {
  height: calc(100vh - 100px);
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
}

/* 对话历史样式 */
.dialog-history-container {
  max-height: 300px;
  overflow-y: auto;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
}

.dialog-turn {
  margin-bottom: 12px;
  padding: 12px;
  background: white;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.dialog-turn:last-child {
  margin-bottom: 0;
}

.turn-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.turn-time {
  font-size: 12px;
  color: #909399;
}

.turn-content {
  font-size: 14px;
  color: #303133;
  line-height: 1.6;
  word-wrap: break-word;
}

.latest-response-container {
  background: #f0f9ff;
  border: 1px solid #b3d8ff;
  border-radius: 8px;
  padding: 12px;
}

.response-content {
  font-size: 14px;
  color: #303133;
  line-height: 1.6;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.toolbar {
  display: flex;
  align-items: center;
  padding: 10px 20px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  gap: 10px;
}

.flow-name {
  font-size: 16px;
  font-weight: 500;
}

.toolbar-right {
  margin-left: auto;
  display: flex;
  gap: 10px;
}

.zoom-controls {
  display: flex;
  align-items: center;
  gap: 5px;
  padding-left: 15px;
  border-left: 1px solid #e4e7ed;
  .el-button {
    margin-left: 0 !important;
  }
}

.zoom-value {
  font-size: 12px;
  color: #606266;
  min-width: 45px;
  text-align: center;
}

.canvas-zoom-controls {
  position: fixed;
  bottom: 30px;
  right: 50px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.95);
  padding: 12px;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  z-index: 100;
  .el-button {
    margin-left: 3px !important;
  }
}

.canvas-zoom-value {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
  min-width: 40px;
  text-align: center;
}

.editor-container {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.node-panel {
  width: 200px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  padding: 10px;
  overflow-y: auto;
  max-height: 100%;
}

.panel-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e4e7ed;
}

.node-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  margin-bottom: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  cursor: grab;
  transition: all 0.2s;
}

.node-item:hover {
  background: #e6f0ff;
  border-color: #409eff;
}

.help-text {
  font-size: 12px;
  color: #909399;
  line-height: 1.8;
}

.flow-container {
  flex: 1;
  background: #fff;
  position: relative;
  overflow: auto;
}

.canvas-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

.canvas {
  position: relative;
  width: 5000px;
  height: 5000px;
  min-width: 100%;
  min-height: 100%;
  background: #fafafa;
  background-image: 
    linear-gradient(rgba(0, 0, 0, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 0, 0, 0.05) 1px, transparent 1px);
  background-size: 20px 20px;
}

.edges-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.workflow-edge {
  fill: none;
  stroke: #409eff;
  stroke-width: 2;
  cursor: pointer;
  pointer-events: stroke;
  transition: stroke-width 0.2s;
}

.workflow-edge:hover,
.workflow-edge.selected {
  stroke-width: 3;
  stroke: #f56c6c;
}

.temp-edge {
  fill: none;
  stroke: #409eff;
  stroke-width: 2;
  stroke-dasharray: 5, 5;
  pointer-events: none;
}

.workflow-node {
  position: absolute;
  padding: 10px 15px;
  border-radius: 8px;
  background: #fff;
  border: 2px solid #e4e7ed;
  min-width: 120px;
  cursor: move;
  transition: all 0.2s;
  user-select: none;
}

.workflow-node:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.workflow-node.selected {
  border-color: #409eff;
  box-shadow: 0 0 10px rgba(64, 158, 255, 0.3);
}

.start-node {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
  color: #fff;
  border-color: #43e97b;
}

.end-node {
  background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
  color: #fff;
  border-color: #fa709a;
}

.input-node {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border-color: #667eea;
}

.output-node {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: #fff;
  border-color: #f093fb;
}

.llm-node {
  background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
  color: #333;
  border-color: #fa709a;
}

.knowledge_retrieval-node {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: #fff;
  border-color: #4facfe;
}

.api-node {
  background: linear-gradient(135deg, #d299c2 0%, #fef9d7 100%);
  color: #333;
  border-color: #d299c2;
}

.message-node {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  border-color: #667eea;
}

.text-node {
  background: linear-gradient(135deg, #a8caba 0%, #5d4e75 100%);
  color: #fff;
  border-color: #a8caba;
}

.image-node {
  background: linear-gradient(135deg, #fccb90 0%, #d57eeb 100%);
  color: #333;
  border-color: #fccb90;
}

.voice-node {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: #fff;
  border-color: #f093fb;
}

.question-node {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: #fff;
  border-color: #4facfe;
}

.condition-node {
  background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);
  color: #fff;
  border-color: #43e97b;
}

.agent-node {
  background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
  color: #333;
  border-color: #a8edea;
}

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-icon {
  font-size: 16px;
}

.node-label {
  font-size: 14px;
  font-weight: 500;
}

.node-content {
  font-size: 12px;
  margin-top: 5px;
  opacity: 0.9;
  word-break: break-all;
  line-height: 1.4;
}

.connection-point {
  position: absolute;
  width: 12px;
  height: 12px;
  background: #409eff;
  border: 2px solid #fff;
  border-radius: 50%;
  cursor: crosshair;
  transition: all 0.2s;
  z-index: 10;
}

.connection-point:hover {
  transform: scale(1.3);
  background: #67c23a;
}

.connection-point.input {
  left: -6px;
  top: 50%;
  transform: translateY(-50%);
}

.connection-point.input:hover {
  transform: translateY(-50%) scale(1.3);
}

.connection-point.output {
  right: -6px;
  top: 50%;
  transform: translateY(-50%);
}

.connection-point.output:hover {
  transform: translateY(-50%) scale(1.3);
}

.config-panel {
  width: 350px;
  min-width: 300px;
  max-width: 400px;
  background: #fff;
  border-left: 1px solid #e4e7ed;
  padding: 10px;
  overflow-y: auto;
}

.edge-info {
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 10px;
}

.edge-info p {
  margin: 5px 0;
  font-size: 13px;
}

/* 微信风格对话框 */
.wechat-style-dialog .el-dialog__body {
  padding: 0;
  height: 600px;
  overflow: hidden;
}

.chat-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 20px;
  overflow: hidden;
}

/* 聊天消息 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 20px;
  min-height: 300px;
  max-height: 400px;
  background: #f5f7fa;
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
  display: flex;
  margin-bottom: 20px;
  animation: messageFadeIn 0.3s ease;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  font-size: 32px;
  margin: 0 10px;
  flex-shrink: 0;
}

.message-content-wrapper {
  max-width: 70%;
  display: flex;
  flex-direction: column;
}

.message-role {
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 4px;
  color: #909399;
}

.message-content {
  padding: 12px 16px;
  border-radius: 18px;
  line-height: 1.5;
  word-wrap: break-word;
}

.message.user .message-content {
  background: #91d5ff;
  color: #303133;
  border-bottom-right-radius: 4px;
}

.message.assistant .message-content {
  background: #fff;
  color: #303133;
  border-bottom-left-radius: 4px;
  border: 1px solid #e4e7ed;
}

.message.message-streaming .message-content::after {
  content: '▋';
  display: inline-block;
  margin-left: 2px;
  animation: typingCursor 1s infinite;
  color: #409eff;
  font-weight: bold;
}

@keyframes typingCursor {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.message-time {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
  align-self: flex-end;
}

.message-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.msg-image {
  max-width: 200px;
  max-height: 200px;
  border-radius: 8px;
  object-fit: cover;
  cursor: pointer;
  transition: transform 0.2s;
}

.msg-image:hover {
  transform: scale(1.02);
}

.image-preview-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.image-preview-item {
  position: relative;
  width: 60px;
  height: 60px;
}

.preview-thumb {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
}

.remove-image {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 18px;
  height: 18px;
  background: #f56c6c;
  color: white;
  border-radius: 50%;
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-btn {
  margin-right: auto;
}

/* 处理过程 */
.message-process {
  margin-top: 10px;
  padding: 10px;
  background: #f0f2f5;
  border-radius: 8px;
  font-size: 13px;
}

.process-item {
  margin-bottom: 8px;
  padding: 8px;
  background: #fff;
  border-radius: 6px;
  border-left: 3px solid #409eff;
  transition: all 0.3s ease;
}

.process-item.collapsed {
  background: #f5f7fa;
}

.process-item.thinking {
  border-left-color: #e6a23c;
}

.process-item.action {
  border-left-color: #409eff;
}

.process-item.result {
  border-left-color: #67c23a;
}

.process-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  cursor: pointer;
  user-select: none;
}

.process-header:hover {
  background: #f0f2f5;
  margin: -4px;
  padding: 4px 8px;
  border-radius: 4px;
}

.process-label {
  font-weight: 600;
  font-size: 12px;
  color: #303133;
}

.process-time {
  font-size: 11px;
  color: #c0c4cc;
  margin-left: 8px;
}

.collapse-icon {
  font-size: 10px;
  color: #909399;
  margin-left: 8px;
  transition: transform 0.3s ease;
}

.process-content {
  font-size: 12px;
  color: #606266;
  line-height: 1.4;
  word-wrap: break-word;
  padding-top: 4px;
}

/* 输入区 */
.chat-input-area {
  padding-top: 20px;
  background: #fff;
  border-top: 1px solid #e4e7ed;
}

.input-textarea {
  margin-bottom: 10px;
  border-radius: 8px;
  resize: none;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.image-preview {
  max-width: 200px;
  max-height: 150px;
  overflow: hidden;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
}

.image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 200px;
  height: 100px;
  background: #f5f7fa;
  border: 1px dashed #d9d9d9;
  border-radius: 4px;
  color: #909399;
  font-size: 12px;
}

/* 动画 */
@keyframes messageFadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>


