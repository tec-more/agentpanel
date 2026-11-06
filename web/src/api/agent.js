import request, { createRequestWithTimeout } from '@/utils/request'

const requestWithLongTimeout = createRequestWithTimeout(300000)

// ==================== 智能体管理 ====================

export function getAgents(params) {
  return request.get('/v1/agent/agents/', { params })
}

export function getAgent(id) {
  return request.get(`/v1/agent/agents/${id}`)
}

export function createAgent(data) {
  return request.post('/v1/agent/agents/', data)
}

export function importAgent(data) {
  return request.post('/v1/agent/agents/import', data)
}

export function updateAgent(id, data) {
  return request.put(`/v1/agent/agents/${id}`, data)
}

export function deleteAgent(id) {
  return request.delete(`/v1/agent/agents/${id}`)
}

export function getAgentSkills(agentId) {
  return request.get(`/v1/agent/agents/${agentId}/skills`)
}

export function addSkillToAgent(agentId, skillId) {
  return request.post(`/v1/agent/agents/${agentId}/skills/${skillId}`)
}

export function removeSkillFromAgent(agentId, skillId) {
  return request.delete(`/v1/agent/agents/${agentId}/skills/${skillId}`)
}

export function setAgentSkills(agentId, skillIds) {
  return request.put(`/v1/agent/agents/${agentId}/skills`, { skill_ids: skillIds })
}

// ==================== 技能管理 ====================

export function getSkills(params) {
  return request.get('/v1/agent/skills/', { params })
}

export function getSkill(id) {
  return request.get(`/v1/agent/skills/${id}`)
}

export function createSkill(data) {
  return request.post('/v1/agent/skills/', data)
}

export function updateSkill(id, data) {
  return request.put(`/v1/agent/skills/${id}`, data)
}

export function deleteSkill(id) {
  return request.delete(`/v1/agent/skills/${id}`)
}

export function getActiveSkills() {
  return request.get('/v1/agent/skills/active/list')
}

export function executeSkill(id, params) {
  return request.post(`/v1/agent/skills/${id}/execute`, params)
}

export function getSkillUsage(id) {
  return request.get(`/v1/agent/skills/${id}/usage`)
}

export function getSkillContent(id) {
  return request.get(`/v1/agent/skills/${id}/content`)
}

export function getSkillsByCategory(categoryId) {
  return request.get(`/v1/agent/skills/category/${categoryId}`)
}

// ==================== 技能分类管理 ====================

export function getSkillCategories(params) {
  return request.get('/v1/agent/skill-categories/', { params })
}

export function getSkillCategory(id) {
  return request.get(`/v1/agent/skill-categories/${id}`)
}

export function createSkillCategory(data) {
  return request.post('/v1/agent/skill-categories/', data)
}

export function updateSkillCategory(id, data) {
  return request.put(`/v1/agent/skill-categories/${id}`, data)
}

export function deleteSkillCategory(id) {
  return request.delete(`/v1/agent/skill-categories/${id}`)
}

export function getSkillCategoryTree() {
  return request.get('/v1/agent/skill-categories/tree/list')
}

export function getActiveSkillCategories() {
  return request.get('/v1/agent/skill-categories/active/list')
}

// ==================== 记忆管理 ====================

export function getMemories(params) {
  return request.get('/v1/agent/memories/', { params })
}

export function getMemory(id) {
  return request.get(`/v1/agent/memories/${id}`)
}

export function createMemory(data) {
  return request.post('/v1/agent/memories/', data)
}

export function updateMemory(id, data) {
  return request.put(`/v1/agent/memories/${id}`, data)
}

export function deleteMemory(id) {
  return request.delete(`/v1/agent/memories/${id}`)
}

export function getMemoriesByAgentAndType(agentId, memoryType) {
  return request.get(`/v1/agent/memories/agent/${agentId}/type/${memoryType}`)
}

export function recallMemory(id, params) {
  return request.post(`/v1/agent/memories/${id}/recall`, params)
}

export function getRecentMemories(agentId) {
  return request.get(`/v1/agent/memories/agent/${agentId}/recent`)
}

// ==================== 工作流管理 ====================

export function getWorkflows(params) {
  return request.get('/v1/agent/workflows/', { params })
}

export function getWorkflow(id) {
  return request.get(`/v1/agent/workflows/${id}`)
}

export function createWorkflow(data) {
  return request.post('/v1/agent/workflows/', data)
}

export function importWorkflow(data) {
  return request.post('/v1/agent/workflows/import', data)
}

export function updateWorkflow(id, data) {
  return request.put(`/v1/agent/workflows/${id}`, data)
}

export function deleteWorkflow(id) {
  return request.delete(`/v1/agent/workflows/${id}`)
}

export function executeWorkflow(id, params) {
  return longRequest.post(`/v1/agent/workflows/${id}/execute`, params)
}

export function getWorkflowExecutions(params) {
  return request.get('/v1/agent/workflow-executions/', { params })
}

export function getWorkflowExecution(id) {
  return request.get(`/v1/agent/workflow-executions/${id}`)
}

// ==================== 对话流管理 ====================

export function getDialogFlows(params) {
  return request.get('/v1/agent/dialog-flows/', { params })
}

export function getDialogFlow(id) {
  return request.get(`/v1/agent/dialog-flows/${id}`)
}

export function createDialogFlow(data) {
  return request.post('/v1/agent/dialog-flows/', data)
}

export function updateDialogFlow(id, data) {
  return request.put(`/v1/agent/dialog-flows/${id}`, data)
}

export function deleteDialogFlow(id) {
  return request.delete(`/v1/agent/dialog-flows/${id}`)
}

export function createDialogFlowNode(dialogFlowId, data) {
  return request.post(`/v1/agent/dialog-flows/${dialogFlowId}/nodes`, data)
}

export function createDialogFlowEdge(dialogFlowId, data) {
  return request.post(`/v1/agent/dialog-flows/${dialogFlowId}/edges`, data)
}

export function executeDialogFlow(id, params) {
  return longRequest.post(`/v1/agent/dialog-flows/${id}/execute`, params)
}

export function executeDialogFlowAuto(id, params, callbacks = {}) {
  const { onStart, onData, onComplete, onError } = callbacks
  
  const safeOnStart = typeof onStart === 'function' ? onStart : () => {}
  const safeOnData = typeof onData === 'function' ? onData : () => {}
  const safeOnComplete = typeof onComplete === 'function' ? onComplete : () => {}
  const safeOnError = typeof onError === 'function' ? onError : () => {}
  
  const abortController = new AbortController()
  let executionId = null
  let isAborted = false

  const controller = {
    abort: () => {
      isAborted = true
      abortController.abort()
    }
  }

  queueMicrotask(async () => {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(`/api/v1/agent/dialog-flows/${id}/execute`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify(params),
        signal: abortController.signal,
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`)
      }

      const contentType = response.headers.get('Content-Type')
      
      if (contentType && contentType.includes('text/event-stream')) {
        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        
        safeOnStart()
        
        let buffer = ''
        
        while (true) {
          if (isAborted || abortController.signal.aborted) {
            break
          }
          
          const { done, value } = await reader.read()
          if (done) {
            break
          }
          
          buffer += decoder.decode(value, { stream: true })
          
          const lines = buffer.split('\n')
          buffer = lines.pop()
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.slice(6).trim()
              if (dataStr) {
                try {
                  const data = JSON.parse(dataStr)
                  if (data.type === 'start' && data.execution_id) {
                    executionId = data.execution_id
                  }
                  console.log('[DialogFlow SSE Stream] Received data:', data)
                  safeOnData(data)
                } catch (e) {
                }
              }
            }
          }
        }
        
        if (!isAborted && !abortController.signal.aborted) {
          safeOnComplete()
        }
      } else {
        safeOnStart()
        
        const result = await response.json()
        
        if (!isAborted) {
          if (result.success) {
            safeOnData({ type: 'complete', result: result.data })
            safeOnComplete(result)
          } else {
            safeOnError(new Error(result.message || '执行失败'))
          }
        }
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        safeOnError(error)
      }
    }
  })

  return controller
}

export function getDialogFlowExecutions(params) {
  return request.get('/v1/agent/dialog-flows/executions', { params })
}

export function getDialogFlowExecution(id) {
  return request.get(`/v1/agent/dialog-flows/executions/${id}`)
}

// ==================== RAG知识库管理 ====================

export function getRAGKnowledgeBases(params) {
  return request.get('/v1/agent/rag/knowledge-bases', { params })
}

export function getRAGKnowledgeBase(id) {
  return request.get(`/v1/agent/rag/knowledge-bases/${id}`)
}

export function createRAGKnowledgeBase(data) {
  return request.post('/v1/agent/rag/knowledge-bases', data)
}

export function updateRAGKnowledgeBase(id, data) {
  return request.put(`/v1/agent/rag/knowledge-bases/${id}`, data)
}

export function deleteRAGKnowledgeBase(id) {
  return request.delete(`/v1/agent/rag/knowledge-bases/${id}`)
}

export function getRAGDocuments(params) {
  return request.get('/v1/agent/rag/documents', { params })
}

export function getRAGDocument(id) {
  return request.get(`/v1/agent/rag/documents/${id}`)
}

export function createRAGDocument(data) {
  return request.post('/v1/agent/rag/documents', data)
}

export function updateRAGDocument(id, data) {
  return request.put(`/v1/agent/rag/documents/${id}`, data)
}

export function deleteRAGDocument(id) {
  return request.delete(`/v1/agent/rag/documents/${id}`)
}

export function processRAGDocument(id, chunk_size = 500, chunk_overlap = 50, split_strategy = "smart", use_llama_index = true) {
    return requestWithLongTimeout.post(`/v1/agent/rag/documents/${id}/process`, null, { params: { chunk_size, chunk_overlap, split_strategy, use_llama_index } })
}

export function batchProcessRAGDocuments(doc_ids, chunk_size = 500, chunk_overlap = 50, split_strategy = "smart", use_llama_index = true) {
    return requestWithLongTimeout.post('/v1/agent/rag/documents/batch-process', {
        doc_ids,
        chunk_size,
        chunk_overlap,
        split_strategy,
        use_llama_index
    })
}

export function searchRAG(data, use_llama_index = null) {
  return requestWithLongTimeout.post('/v1/agent/rag/search', data, { params: { use_llama_index } })
}

export function getRAGDocumentChunks(docId, params) {
  return request.get(`/v1/agent/rag/documents/${docId}/chunks`, { params })
}

export function deleteRAGChunk(id) {
  return request.delete(`/v1/agent/rag/chunks/${id}`)
}

export function uploadRAGDocument(knowledgeBaseId, file) {
  const formData = new FormData()
  formData.append('file', file)
  return requestWithLongTimeout.post(`/v1/agent/rag/documents/upload?knowledge_base_id=${knowledgeBaseId}`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

export function getDepartments(params) {
  return request.get('/v1/departments/list', { params })
}

// ==================== 工具管理 ====================

export function getTools(params) {
  return request.get('/v1/agent/tools/', { params })
}

export function getTool(id) {
  return request.get(`/v1/agent/tools/${id}`)
}

export function createTool(data) {
  return request.post('/v1/agent/tools/', data)
}

export function updateTool(id, data) {
  return request.put(`/v1/agent/tools/${id}`, data)
}

export function deleteTool(id) {
  return request.delete(`/v1/agent/tools/${id}`)
}

export function getActiveTools() {
  return request.get('/v1/agent/tools/active/list')
}

// ==================== 工具标签管理 ====================

export function getToolTags(params) {
  return request.get('/v1/agent/tool-tags/', { params })
}

export function getToolTag(id) {
  return request.get(`/v1/agent/tool-tags/${id}`)
}

export function createToolTag(data) {
  return request.post('/v1/agent/tool-tags/', data)
}

export function updateToolTag(id, data) {
  return request.put(`/v1/agent/tool-tags/${id}`, data)
}

export function deleteToolTag(id) {
  return request.delete(`/v1/agent/tool-tags/${id}`)
}

export function getActiveToolTags() {
  return request.get('/v1/agent/tool-tags/active/list')
}

export function getToolTagsWithCount() {
  return request.get('/v1/agent/tool-tags/with-count')
}

// ==================== 工具函数 ====================

export function hasStreamingLLMNode(graphDefinition) {
  if (!graphDefinition || !graphDefinition.nodes) {
    return false
  }
  
  return graphDefinition.nodes.some(node => {
    if (node.type === 'llm' && node.data) {
      return node.data.stream === true
    }
    return false
  })
}
