import request from '@/utils/request'

const BASE = '/v1/inventory'

export const getWarehouseList = (params) => {
  return request.get(`${BASE}/warehouses`, { params })
}

export const getWarehouseDetail = (id) => {
  return request.get(`${BASE}/warehouses/${id}`)
}

export const createWarehouse = (data) => {
  return request.post(`${BASE}/warehouses`, data)
}

export const updateWarehouse = (id, data) => {
  return request.put(`${BASE}/warehouses/${id}`, data)
}

export const deleteWarehouse = (id) => {
  return request.delete(`${BASE}/warehouses/${id}`)
}

export const getLocationList = (params) => {
  return request.get(`${BASE}/locations`, { params })
}

export const getLocationDetail = (id) => {
  return request.get(`${BASE}/locations/${id}`)
}

export const createLocation = (data) => {
  return request.post(`${BASE}/locations`, data)
}

export const updateLocation = (id, data) => {
  return request.put(`${BASE}/locations/${id}`, data)
}

export const deleteLocation = (id) => {
  return request.delete(`${BASE}/locations/${id}`)
}

export const getPickingTypeList = (params) => {
  return request.get(`${BASE}/picking-types`, { params })
}

export const getPickingTypeDetail = (id) => {
  return request.get(`${BASE}/picking-types/${id}`)
}

export const createPickingType = (data) => {
  return request.post(`${BASE}/picking-types`, data)
}

export const updatePickingType = (id, data) => {
  return request.put(`${BASE}/picking-types/${id}`, data)
}

export const deletePickingType = (id) => {
  return request.delete(`${BASE}/picking-types/${id}`)
}

export const getLotList = (params) => {
  return request.get(`${BASE}/lots`, { params })
}

export const getLotDetail = (id) => {
  return request.get(`${BASE}/lots/${id}`)
}

export const createLot = (data) => {
  return request.post(`${BASE}/lots`, data)
}

export const updateLot = (id, data) => {
  return request.put(`${BASE}/lots/${id}`, data)
}

export const deleteLot = (id) => {
  return request.delete(`${BASE}/lots/${id}`)
}

export const getPackageList = (params) => {
  return request.get(`${BASE}/packages`, { params })
}

export const getPackageDetail = (id) => {
  return request.get(`${BASE}/packages/${id}`)
}

export const createPackage = (data) => {
  return request.post(`${BASE}/packages`, data)
}

export const updatePackage = (id, data) => {
  return request.put(`${BASE}/packages/${id}`, data)
}

export const deletePackage = (id) => {
  return request.delete(`${BASE}/packages/${id}`)
}

export const getQuantList = (params) => {
  return request.get(`${BASE}/quants`, { params })
}

export const getQuantDetail = (id) => {
  return request.get(`${BASE}/quants/${id}`)
}

export const getQuantSummary = (params) => {
  return request.get(`${BASE}/quants/summary`, { params })
}

export const getQuantsByProduct = (productCode) => {
  return request.get(`${BASE}/quants/by-product/${productCode}`)
}

export const getQuantsByLocation = (locationId) => {
  return request.get(`${BASE}/quants/by-location/${locationId}`)
}

export const getReservationList = (params) => {
  return request.get(`${BASE}/quants/reservations`, { params })
}

export const getPickingList = (params) => {
  return request.get(`${BASE}/pickings`, { params })
}

export const getPickingDetail = (id) => {
  return request.get(`${BASE}/pickings/${id}`)
}

export const createPicking = (data) => {
  return request.post(`${BASE}/pickings`, data)
}

export const updatePicking = (id, data) => {
  return request.put(`${BASE}/pickings/${id}`, data)
}

export const deletePicking = (id) => {
  return request.delete(`${BASE}/pickings/${id}`)
}

export const confirmPicking = (id) => {
  return request.post(`${BASE}/pickings/${id}/confirm`)
}

export const assignPicking = (id) => {
  return request.post(`${BASE}/pickings/${id}/assign`)
}

export const doPicking = (id) => {
  return request.post(`${BASE}/pickings/${id}/do`)
}

export const cancelPicking = (id) => {
  return request.post(`${BASE}/pickings/${id}/cancel`)
}
