import request from '@/utils/request'

// ============ 内容中心 ============
export const getContentList = (params) => request.get('/v1/contentops/contents', { params })
export const getContentDetail = (id) => request.get(`/v1/contentops/contents/${id}`)
export const createContent = (data) => request.post('/v1/contentops/contents', data)
export const updateContent = (id, data) => request.put(`/v1/contentops/contents/${id}`, data)
export const deleteContent = (id) => request.delete(`/v1/contentops/contents/${id}`)
export const updateVersion = (versionId, data) => request.put(`/v1/contentops/contents/versions/${versionId}`, data)
export const rollbackVersion = (versionId) => request.post(`/v1/contentops/contents/versions/${versionId}/rollback`)
export const confirmVersion = (versionId, confirm = true) =>
  request.post(`/v1/contentops/contents/versions/${versionId}/confirm`, { confirm })
export const generateAdapt = (data) => request.post('/v1/contentops/contents/adapt/generate', data)

// ============ 合规检测 ============
export const checkCompliance = (data) => request.post('/v1/contentops/compliance/check', data)

// ============ 审核 ============
export const getReviewQueue = (status = 'pending') =>
  request.get('/v1/contentops/reviews', { params: { status } })
export const decideReview = (taskId, data) => request.post(`/v1/contentops/reviews/${taskId}/decide`, data)

// ============ 成品导出 ============
export const createExport = (data) => request.post('/v1/contentops/exports', data)
export const getExportList = () => request.get('/v1/contentops/exports')
export const downloadExport = (packageId) =>
  request.get(`/v1/contentops/exports/${packageId}/download`, { responseType: 'blob' })

// ============ 发布台账 ============
export const getLedgerList = (params) => request.get('/v1/contentops/ledger', { params })
export const createLedger = (data) => request.post('/v1/contentops/ledger', data)
export const updateLedger = (id, data) => request.put(`/v1/contentops/ledger/${id}`, data)
export const addEffect = (ledgerId, data) => request.post(`/v1/contentops/ledger/${ledgerId}/effect`, data)
export const importEffect = (ledgerId, data) => request.post(`/v1/contentops/ledger/${ledgerId}/effect/import`, data)
export const getEffect = (ledgerId) => request.get(`/v1/contentops/ledger/${ledgerId}/effect`)

// ============ 规则库 ============
export const getRuleList = (params) => request.get('/v1/contentops/rules', { params })
export const createRule = (data) => request.post('/v1/contentops/rules', data)
export const updateRule = (id, data) => request.put(`/v1/contentops/rules/${id}`, data)
export const deleteRule = (id) => request.delete(`/v1/contentops/rules/${id}`)
export const getPlatformRules = (platform) => request.get(`/v1/contentops/rules/platform/${platform}`)
export const setPlatformRule = (platform, key, value) =>
  request.put(`/v1/contentops/rules/platform/${platform}/${key}`, value)

// ============ 平台常量 ============
export const PLATFORMS = [
  { value: 'wechat', label: '微信公众号' },
  { value: 'weibo', label: '微博' },
  { value: 'xiaohongshu', label: '小红书' },
  { value: 'douyin', label: '抖音' },
  { value: 'toutiao', label: '今日头条' },
  { value: 'bilibili', label: 'B站' }
]
