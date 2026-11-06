import request from '@/utils/request'

export const getSupplierList = (params) => {
  return request.get('/v1/purchase/supplier/', { params })
}

export const getSupplierDetail = (id) => {
  return request.get(`/v1/purchase/supplier/${id}`)
}

export const createSupplier = (data) => {
  return request.post('/v1/purchase/supplier/', data)
}

export const updateSupplier = (id, data) => {
  return request.put(`/v1/purchase/supplier/${id}`, data)
}

export const deleteSupplier = (id) => {
  return request.delete(`/v1/purchase/supplier/${id}`)
}

export const getActiveSuppliers = () => {
  return request.get('/v1/purchase/supplier/active/list')
}

export const getPurchaseOrderList = (params) => {
  return request.get('/v1/purchase/order/', { params })
}

export const getPurchaseOrderDetail = (id) => {
  return request.get(`/v1/purchase/order/${id}`)
}

export const createPurchaseOrder = (data) => {
  return request.post('/v1/purchase/order/', data)
}

export const updatePurchaseOrder = (id, data) => {
  return request.put(`/v1/purchase/order/${id}`, data)
}

export const confirmPurchaseOrder = (id) => {
  return request.post(`/v1/purchase/order/${id}/confirm`)
}

export const cancelPurchaseOrder = (id) => {
  return request.post(`/v1/purchase/order/${id}/cancel`)
}

export const deletePurchaseOrder = (id) => {
  return request.delete(`/v1/purchase/order/${id}`)
}

export const getPurchaseReceiptList = (params) => {
  return request.get('/v1/purchase/order/receipt/', { params })
}

export const getPurchaseReceiptDetail = (id) => {
  return request.get(`/v1/purchase/order/receipt/${id}`)
}

export const createPurchaseReceipt = (data) => {
  return request.post('/v1/purchase/order/receipt/', data)
}

export const updatePurchaseReceipt = (id, data) => {
  return request.put(`/v1/purchase/order/receipt/${id}`, data)
}

export const deletePurchaseReceipt = (id) => {
  return request.delete(`/v1/purchase/order/receipt/${id}`)
}