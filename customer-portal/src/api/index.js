import request from '@/utils/request'

// ---------- 认证 ----------
export const apiLogin = (data) => request.post('/v1/customer/auth/login', data)
export const apiSendCode = (data) => request.post('/v1/customer/auth/send-code', data)
export const apiLoginByCode = (data) => request.post('/v1/customer/auth/login-code', data)
export const apiAuthMe = () => request.get('/v1/customer/auth/me')

// ---------- 自助 ----------
export const apiMyProfile = () => request.get('/v1/customer/me/profile')
export const apiMyMembership = () => request.get('/v1/customer/me/membership')
export const apiMyOrders = (params) => request.get('/v1/customer/me/orders', { params })
export const apiMyPayments = (params) => request.get('/v1/customer/me/payments', { params })
export const apiMyOrganizations = () => request.get('/v1/customer/me/organizations')

// ---------- 工作台 ----------
export const apiCheck = (data, idempotencyKey) =>
  request.post('/v1/customer/workspace/compliance/check', data, {
    headers: idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}
  })
export const apiWorkspaceRules = (params) => request.get('/v1/customer/workspace/rules', { params })
