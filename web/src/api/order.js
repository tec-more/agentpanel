import request from '@/utils/request'

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

export const cancelOrder = (id) => {
  return request.patch(`/v1/sales/orders/${id}/status`, { status: 'cancelled' })
}

export const completeOrder = (id) => {
  return request.patch(`/v1/sales/orders/${id}/status`, { status: 'completed' })
}
