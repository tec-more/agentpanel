import request from '@/utils/request'

// 线索管理
export const getLeadList = (params) => {
  return request.get('/v1/crm/leads', { params })
}
export const getLeadDetail = (id) => {
  return request.get(`/v1/crm/leads/${id}`)
}
export const createLead = (data) => {
  return request.post('/v1/crm/leads', data)
}
export const updateLead = (id, data) => {
  return request.put(`/v1/crm/leads/${id}`, data)
}
export const deleteLead = (id) => {
  return request.delete(`/v1/crm/leads/${id}`)
}
export const convertLead = (id) => {
  return request.post(`/v1/crm/leads/${id}/convert`)
}
export const assignLead = (id, data) => {
  return request.post(`/v1/crm/leads/${id}/assign`, data)
}

// 商机管理
export const getOpportunityList = (params) => {
  return request.get('/v1/crm/opportunities', { params })
}
export const getOpportunityKanban = () => {
  return request.get('/v1/crm/opportunities/kanban')
}
export const getOpportunityDetail = (id) => {
  return request.get(`/v1/crm/opportunities/${id}`)
}
export const createOpportunity = (data) => {
  return request.post('/v1/crm/opportunities', data)
}
export const updateOpportunity = (id, data) => {
  return request.put(`/v1/crm/opportunities/${id}`, data)
}
export const deleteOpportunity = (id) => {
  return request.delete(`/v1/crm/opportunities/${id}`)
}
export const advanceOpportunityStage = (id, data) => {
  return request.post(`/v1/crm/opportunities/${id}/advance`, data)
}
export const winOpportunity = (id, data) => {
  return request.post(`/v1/crm/opportunities/${id}/win`, data)
}
export const loseOpportunity = (id, data) => {
  return request.post(`/v1/crm/opportunities/${id}/lose`, data)
}

// 活动管理
export const getActivityList = (params) => {
  return request.get('/v1/crm/activities', { params })
}
export const getActivityTimeline = (params) => {
  return request.get('/v1/crm/activities/timeline', { params })
}
export const createActivity = (data) => {
  return request.post('/v1/crm/activities', data)
}
export const deleteActivity = (id) => {
  return request.delete(`/v1/crm/activities/${id}`)
}

// 联系人管理
export const getContactList = (params) => {
  return request.get('/v1/crm/contacts', { params })
}
export const createContact = (data) => {
  return request.post('/v1/crm/contacts', data)
}
export const updateContact = (id, data) => {
  return request.put(`/v1/crm/contacts/${id}`, data)
}
export const deleteContact = (id) => {
  return request.delete(`/v1/crm/contacts/${id}`)
}
export const setPrimaryContact = (id) => {
  return request.post(`/v1/crm/contacts/${id}/set-primary`)
}

// 跟进任务
export const getTaskList = (params) => {
  return request.get('/v1/crm/tasks', { params })
}
export const getMyTasks = () => {
  return request.get('/v1/crm/tasks/mine')
}
export const createTask = (data) => {
  return request.post('/v1/crm/tasks', data)
}
export const updateTask = (id, data) => {
  return request.put(`/v1/crm/tasks/${id}`, data)
}
export const completeTask = (id, data) => {
  return request.post(`/v1/crm/tasks/${id}/complete`, data)
}
export const cancelTask = (id) => {
  return request.post(`/v1/crm/tasks/${id}/cancel`)
}

// 统计分析
export const getFunnelStats = () => {
  return request.get('/v1/crm/stats/funnel')
}
export const getLeadSourceStats = () => {
  return request.get('/v1/crm/stats/lead-sources')
}
export const getSalesPerformance = () => {
  return request.get('/v1/crm/stats/sales-performance')
}
export const getCustomerFollowUp = () => {
  return request.get('/v1/crm/stats/customer-follow-up')
}

// 系统配置
export const getStages = () => {
  return request.get('/v1/crm/config/stages')
}
export const saveStage = (data) => {
  return request.post('/v1/crm/config/stages', data)
}
export const updateStage = (id, data) => {
  return request.put(`/v1/crm/config/stages/${id}`, data)
}
export const deleteStage = (id) => {
  return request.delete(`/v1/crm/config/stages/${id}`)
}
export const getLeadSources = () => {
  return request.get('/v1/crm/config/lead-sources')
}
export const saveLeadSource = (data) => {
  return request.post('/v1/crm/config/lead-sources', data)
}
export const updateLeadSource = (id, data) => {
  return request.put(`/v1/crm/config/lead-sources/${id}`, data)
}
export const deleteLeadSource = (id) => {
  return request.delete(`/v1/crm/config/lead-sources/${id}`)
}
export const getSettings = () => {
  return request.get('/v1/crm/config/settings')
}
export const updateSettings = (data) => {
  return request.put('/v1/crm/config/settings', data)
}
