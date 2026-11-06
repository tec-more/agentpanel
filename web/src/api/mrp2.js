import request from '@/utils/request'

const BASE = '/v1/mrp2'

export const getForecastList = (params) => {
  return request.get(`${BASE}/forecast`, { params })
}

export const getForecastDetail = (id) => {
  return request.get(`${BASE}/forecast/${id}`)
}

export const createForecast = (data) => {
  return request.post(`${BASE}/forecast`, data)
}

export const updateForecast = (id, data) => {
  return request.put(`${BASE}/forecast/${id}`, data)
}

export const deleteForecast = (id) => {
  return request.delete(`${BASE}/forecast/${id}`)
}

export const submitForecast = (id) => {
  return request.put(`${BASE}/forecast/${id}/submit`)
}

export const approveForecast = (id) => {
  return request.put(`${BASE}/forecast/${id}/approve`)
}

export const rejectForecast = (id) => {
  return request.put(`${BASE}/forecast/${id}/reject`)
}

export const getMpsList = (params) => {
  return request.get(`${BASE}/mps`, { params })
}

export const getMpsDetail = (id) => {
  return request.get(`${BASE}/mps/${id}`)
}

export const createMps = (data) => {
  return request.post(`${BASE}/mps`, data)
}

export const updateMps = (id, data) => {
  return request.put(`${BASE}/mps/${id}`, data)
}

export const deleteMps = (id) => {
  return request.delete(`${BASE}/mps/${id}`)
}

export const compileMps = (id) => {
  return request.post(`${BASE}/mps/${id}/compile`)
}

export const submitMps = (id) => {
  return request.put(`${BASE}/mps/${id}/submit`)
}

export const approveMps = (id, data) => {
  return request.put(`${BASE}/mps/${id}/approve`, data)
}

export const releaseMps = (id) => {
  return request.put(`${BASE}/mps/${id}/release`)
}

export const closeMps = (id) => {
  return request.put(`${BASE}/mps/${id}/close`)
}

export const cancelMps = (id) => {
  return request.put(`${BASE}/mps/${id}/cancel`)
}

export const getMpsPlanLines = (id) => {
  return request.get(`${BASE}/mps/${id}/plan-lines`)
}

export const adjustMpsPlanLine = (lineId, data) => {
  return request.put(`${BASE}/mps/plan-lines/${lineId}/adjust`, data)
}

export const getMrpList = (params) => {
  return request.get(`${BASE}/mrp`, { params })
}

export const getMrpDetail = (id) => {
  return request.get(`${BASE}/mrp/${id}`)
}

export const createMrp = (data) => {
  return request.post(`${BASE}/mrp`, data)
}

export const calculateMrp = (data) => {
  return request.post(`${BASE}/mrp/calculate`, data)
}

export const deleteMrp = (id) => {
  return request.delete(`${BASE}/mrp/${id}`)
}

export const getMrpPlannedOrders = (mrpId) => {
  return request.get(`${BASE}/mrp/${mrpId}/planned-orders`)
}

export const getPlannedOrderList = (params) => {
  return request.get(`${BASE}/planned-order`, { params })
}

export const getPlannedOrderDetail = (id) => {
  return request.get(`${BASE}/planned-order/${id}`)
}

export const confirmPlannedOrder = (id, data) => {
  return request.post(`${BASE}/planned-order/${id}/confirm`, data)
}

export const cancelPlannedOrder = (id) => {
  return request.post(`${BASE}/planned-order/${id}/cancel`)
}

export const getCrpList = (params) => {
  return request.get(`${BASE}/crp`, { params })
}

export const getCrpDetail = (id) => {
  return request.get(`${BASE}/crp/${id}`)
}

export const createCrp = (data) => {
  return request.post(`${BASE}/crp`, data)
}

export const calculateCrp = (data) => {
  return request.post(`${BASE}/crp/calculate`, data)
}

export const deleteCrp = (id) => {
  return request.delete(`${BASE}/crp/${id}`)
}

export const getMonitorList = (params) => {
  return request.get(`${BASE}/monitor`, { params })
}

export const getMonitorDetail = (id) => {
  return request.get(`${BASE}/monitor/${id}`)
}

export const createMonitor = (data) => {
  return request.post(`${BASE}/monitor`, data)
}

export const updateMonitor = (id, data) => {
  return request.put(`${BASE}/monitor/${id}`, data)
}

export const deleteMonitor = (id) => {
  return request.delete(`${BASE}/monitor/${id}`)
}

export const pauseMonitor = (id) => {
  return request.put(`${BASE}/monitor/${id}/pause`)
}

export const resumeMonitor = (id) => {
  return request.put(`${BASE}/monitor/${id}/resume`)
}