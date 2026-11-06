import request from '@/utils/request'

const BASE = '/v1/quality'

export const getInspectionList = (params) => {
  return request.get(`${BASE}/inspections`, { params })
}

export const getInspectionDetail = (id) => {
  return request.get(`${BASE}/inspections/${id}`)
}

export const createInspection = (data) => {
  return request.post(`${BASE}/inspections`, data)
}

export const updateInspection = (id, data) => {
  return request.put(`${BASE}/inspections/${id}`, data)
}

export const deleteInspection = (id) => {
  return request.delete(`${BASE}/inspections/${id}`)
}

export const submitInspection = (id, data) => {
  return request.post(`${BASE}/inspections/${id}/submit`, data)
}

export const getStandardList = (params) => {
  return request.get(`${BASE}/standards`, { params })
}

export const getStandardDetail = (id) => {
  return request.get(`${BASE}/standards/${id}`)
}

export const createStandard = (data) => {
  return request.post(`${BASE}/standards`, data)
}

export const updateStandard = (id, data) => {
  return request.put(`${BASE}/standards/${id}`, data)
}

export const deleteStandard = (id) => {
  return request.delete(`${BASE}/standards/${id}`)
}