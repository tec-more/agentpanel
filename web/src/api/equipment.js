import request from '@/utils/request'

const BASE = '/v1/equipment'

export const getEquipmentList = (params) => {
  return request.get(`${BASE}/equipment`, { params })
}

export const getEquipmentDetail = (id) => {
  return request.get(`${BASE}/equipment/${id}`)
}

export const createEquipment = (data) => {
  return request.post(`${BASE}/equipment`, data)
}

export const updateEquipment = (id, data) => {
  return request.put(`${BASE}/equipment/${id}`, data)
}

export const deleteEquipment = (id) => {
  return request.delete(`${BASE}/equipment/${id}`)
}

export const changeEquipmentStatus = (id, status) => {
  return request.post(`${BASE}/equipment/${id}/status`, { status })
}

export const getMaintenanceList = (params) => {
  return request.get(`${BASE}/maintenance`, { params })
}

export const getMaintenanceDetail = (id) => {
  return request.get(`${BASE}/maintenance/${id}`)
}

export const createMaintenance = (data) => {
  return request.post(`${BASE}/maintenance`, data)
}

export const updateMaintenance = (id, data) => {
  return request.put(`${BASE}/maintenance/${id}`, data)
}

export const deleteMaintenance = (id) => {
  return request.delete(`${BASE}/maintenance/${id}`)
}

export const completeMaintenance = (id, operator) => {
  return request.post(`${BASE}/maintenance/${id}/complete`, { operator })
}

export const getFaultList = (params) => {
  return request.get(`${BASE}/fault`, { params })
}

export const getFaultDetail = (id) => {
  return request.get(`${BASE}/fault/${id}`)
}

export const createFault = (data) => {
  return request.post(`${BASE}/fault`, data)
}

export const updateFault = (id, data) => {
  return request.put(`${BASE}/fault/${id}`, data)
}

export const deleteFault = (id) => {
  return request.delete(`${BASE}/fault/${id}`)
}

export const processFault = (id, operator) => {
  return request.post(`${BASE}/fault/${id}/process`, { operator })
}

export const resolveFault = (id, solution, operator) => {
  return request.post(`${BASE}/fault/${id}/resolve`, { solution, operator })
}

export const closeFault = (id) => {
  return request.post(`${BASE}/fault/${id}/close`)
}