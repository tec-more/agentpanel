import request from '@/utils/request'

const BASE = '/v1/document'

// 分类管理
export const getCategoryList = (params) => {
  return request.get(`${BASE}/categories`, { params })
}

export const getCategoryTree = () => {
  return request.get(`${BASE}/categories/tree`)
}

export const getCategoryDetail = (id) => {
  return request.get(`${BASE}/categories/${id}`)
}

export const createCategory = (data) => {
  return request.post(`${BASE}/categories`, data)
}

export const updateCategory = (id, data) => {
  return request.put(`${BASE}/categories/${id}`, data)
}

export const deleteCategory = (id) => {
  return request.delete(`${BASE}/categories/${id}`)
}

// 文档管理
export const getDocumentList = (params) => {
  return request.get(`${BASE}/documents`, { params })
}

export const getDocumentDetail = (id) => {
  return request.get(`${BASE}/documents/${id}`)
}

export const createDocument = (data) => {
  return request.post(`${BASE}/documents`, data)
}

export const uploadDocument = (formData) => {
  return request.post(`${BASE}/documents/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export const updateDocument = (id, data) => {
  return request.put(`${BASE}/documents/${id}`, data)
}

export const deleteDocument = (id) => {
  return request.delete(`${BASE}/documents/${id}`)
}

export const batchDeleteDocuments = (data) => {
  return request.post(`${BASE}/documents/batch-delete`, data)
}

export const batchRestoreDocuments = (data) => {
  return request.post(`${BASE}/documents/batch-restore`, data)
}

export const permanentDeleteDocument = (id) => {
  return request.delete(`${BASE}/documents/${id}/permanent`)
}

export const moveDocument = (id, data) => {
  return request.post(`${BASE}/documents/${id}/move`, data)
}

export const getTrashList = (params) => {
  return request.get(`${BASE}/documents/trash`, { params })
}

export const getDocumentStatistics = () => {
  return request.get(`${BASE}/documents/statistics`)
}

export const getDocumentsByBusiness = (type, id) => {
  return request.get(`${BASE}/documents/business/${type}/${id}`)
}

// 版本管理
export const getVersionList = (documentId, params) => {
  return request.get(`${BASE}/versions/document/${documentId}`, { params })
}

export const getVersionDetail = (versionId) => {
  return request.get(`${BASE}/versions/${versionId}`)
}

export const createVersion = (documentId, data) => {
  return request.post(`${BASE}/versions/document/${documentId}`, data)
}

export const uploadDocumentNewVersion = (documentId, formData) => {
  return request.post(`${BASE}/versions/document/${documentId}/upload`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export const updateVersion = (versionId, data) => {
  return request.put(`${BASE}/versions/${versionId}`, data)
}

export const deleteVersion = (versionId) => {
  return request.delete(`${BASE}/versions/${versionId}`)
}

export const rollbackVersion = (documentId, data) => {
  return request.post(`${BASE}/versions/document/${documentId}/rollback`, data)
}

// 预览
export const checkPreviewable = (documentId) => {
  return request.get(`${BASE}/preview/${documentId}/check`)
}

export const getPreviewUrl = (documentId) => {
  return `${BASE}/preview/${documentId}`
}

export const getDownloadUrl = (documentId) => {
  return `${BASE}/preview/${documentId}/download`
}

// RAG 集成
export const linkToKnowledgeBase = (documentId, data) => {
  return request.post(`${BASE}/rag/documents/${documentId}/link`, data)
}

export const batchLinkToKnowledgeBase = (data) => {
  return request.post(`${BASE}/rag/documents/batch-link`, data)
}

export const unlinkFromKnowledgeBase = (documentId) => {
  return request.post(`${BASE}/rag/documents/${documentId}/unlink`)
}

export const getLinkedDocuments = (knowledgeBaseId) => {
  return request.get(`${BASE}/rag/knowledge-bases/${knowledgeBaseId}/documents`)
}

export const reprocessDocument = (documentId) => {
  return request.post(`${BASE}/rag/documents/${documentId}/reprocess`)
}

export const syncFromRag = (ragDocumentId, data) => {
  return request.post(`${BASE}/rag/rag-documents/${ragDocumentId}/sync`, data)
}

export const batchSyncFromRag = (data) => {
  return request.post(`${BASE}/rag/rag-documents/batch-sync`, data)
}
