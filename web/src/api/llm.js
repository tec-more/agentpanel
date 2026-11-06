import request from '@/utils/request'

// ============ 厂商管理 ============

// 获取厂商列表
export const getProviderList = (params) => {
  return request.get('/v1/llm/providers', { params })
}

// 获取厂商详情
export const getProviderDetail = (id) => {
  return request.get(`/v1/llm/providers/${id}`)
}

// 创建厂商
export const createProvider = (data) => {
  return request.post('/v1/llm/providers', data)
}

// 更新厂商
export const updateProvider = (id, data) => {
  return request.put(`/v1/llm/providers/${id}`, data)
}

// 删除厂商
export const deleteProvider = (id) => {
  return request.delete(`/v1/llm/providers/${id}`)
}

// ============ 大模型管理 ============

// 获取大模型列表
export const getModelList = (params) => {
  return request.get('/v1/llm/models', { params })
}

// 获取大模型详情
export const getModelDetail = (id) => {
  return request.get(`/v1/llm/models/${id}`)
}

// 创建大模型
export const createModel = (data) => {
  return request.post('/v1/llm/models', data)
}

// 更新大模型
export const updateModel = (id, data) => {
  return request.put(`/v1/llm/models/${id}`, data)
}

// 删除大模型
export const deleteModel = (id) => {
  return request.delete(`/v1/llm/models/${id}`)
}

// ============ API密钥管理 ============

// 获取API密钥列表
export const getApiKeyList = (params) => {
  return request.get('/v1/llm/api-keys', { params })
}

// 获取API密钥详情
export const getApiKeyDetail = (id) => {
  return request.get(`/v1/llm/api-keys/${id}`)
}

// 创建API密钥
export const createApiKey = (data) => {
  return request.post('/v1/llm/api-keys', data)
}

// 更新API密钥
export const updateApiKey = (id, data) => {
  return request.put(`/v1/llm/api-keys/${id}`, data)
}

// 删除API密钥
export const deleteApiKey = (id) => {
  return request.delete(`/v1/llm/api-keys/${id}`)
}

// 重置配额
export const resetApiKeyQuota = (id) => {
  return request.post(`/v1/llm/api-keys/${id}/reset-quota`)
}

// 测试API密钥
export const testApiKey = (id) => {
  return request.get(`/v1/llm/api-keys/${id}/test`)
}

// ============ 使用统计管理 ============

// 获取使用记录列表
export const getUsageRecords = (params) => {
  return request.get('/v1/llm/usage/records', { params })
}

// 获取使用统计
export const getUsageStatistics = (params) => {
  return request.get('/v1/llm/usage/statistics', { params })
}

// 获取每日使用统计
export const getDailyStatistics = (params) => {
  return request.get('/v1/llm/usage/statistics/daily', { params })
}

// 获取模型使用统计
export const getModelStatistics = (params) => {
  return request.get('/v1/llm/usage/statistics/model', { params })
}

// 获取客户使用统计
export const getCustomerStatistics = (params) => {
  return request.get('/v1/llm/usage/statistics/customer', { params })
}

// 获取统一使用记录列表
export const getUnifiedUsageRecords = (params) => {
  return request.get('/v1/llm/usage/unified-records', { params })
}

// ============ 语音服务 ============

// 流式语音识别
export const streamingASR = (formData) => {
  return request.post('/v1/llm/voice/asr/streaming', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 录音文件识别
export const fileASR = (formData) => {
  return request.post('/v1/llm/voice/asr/file', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 语音合成
export const textToSpeech = (formData) => {
  return request.post('/v1/llm/voice/tts', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    responseType: 'blob'
  })
}

// 提交声音复刻任务
export const submitVoiceClone = (formData) => {
  return request.post('/v1/llm/voice/clone/submit', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 查询声音复刻状态
export const checkCloneStatus = (cloneId, params) => {
  return request.get(`/v1/llm/voice/clone/${cloneId}`, { params })
}

// 同声传译
export const streamingTranslation = (formData) => {
  return request.post('/v1/llm/voice/translation/streaming', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
