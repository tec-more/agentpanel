import request from '@/utils/request'

export const getSalesOverview = (params) => {
  return request.get('/v1/sales/stats/overview', { params })
}

export const getDailySales = (params) => {
  return request.get('/v1/sales/stats/daily', { params })
}

export const getMonthlySales = (params) => {
  return request.get('/v1/sales/stats/monthly', { params })
}

export const getTopProducts = (limit = 10, params) => {
  return request.get('/v1/sales/stats/top-products', { params: { limit, ...params } })
}

export const getTopCustomers = (limit = 10, params) => {
  return request.get('/v1/sales/stats/top-customers', { params: { limit, ...params } })
}

export const getPaymentMethodStats = (params) => {
  return request.get('/v1/sales/stats/payment-methods', { params })
}

export const getOrderList = (params) => {
  return request.get('/v1/sales/orders/', { params })
}

export const getOrderDetail = (id) => {
  return request.get(`/v1/sales/orders/${id}`)
}

export const createOrder = (data) => {
  return request.post('/v1/sales/orders/create', data)
}

export const updateOrder = (id, data) => {
  return request.put(`/v1/sales/orders/${id}`, data)
}

export const deleteOrder = (id) => {
  return request.delete(`/v1/sales/orders/${id}`)
}

export const batchDeleteOrder = (ids) => {
  return request.delete('/v1/sales/orders/batch', { data: { ids } })
}

export const getOrdersByCustomer = (customerId, params) => {
  return request.get(`/v1/sales/orders/customer/${customerId}`, { params })
}

export const updateOrderStatus = (id, data) => {
  return request.patch(`/v1/sales/orders/${id}/status`, data)
}

export const updatePaymentStatus = (id, data) => {
  return request.patch(`/v1/sales/orders/${id}/payment-status`, data)
}
