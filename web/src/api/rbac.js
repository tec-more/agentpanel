import request from '@/utils/request'

// ==================== 角色管理 ==================== //

// 获取角色列表
export function getRoleList(params) {
  return request.get('/v1/rbac/roles/list', { params })
}

// 获取角色详情
export function getRoleDetail(roleId) {
  return request.get(`/v1/rbac/roles/${roleId}`)
}

// 创建角色
export function createRole(data) {
  return request.post('/v1/rbac/roles', data)
}

// 更新角色
export function updateRole(roleId, data) {
  return request.put(`/v1/rbac/roles/${roleId}`, data)
}

// 删除角色
export function deleteRole(roleId) {
  return request.delete(`/v1/rbac/roles/${roleId}`)
}

// 获取角色的权限
export function getRolePermissions(roleId) {
  return request.get(`/v1/rbac/roles/${roleId}`)
}

// 设置角色的权限
export function setRolePermissions(roleId, permissionIds) {
  return request.post(`/v1/rbac/roles/${roleId}/permissions`, { permission_ids: permissionIds })
}

// ==================== 菜单管理 ==================== //

// 获取菜单树形结构
export function getMenuTree() {
  return request.get('/v1/menus/tree')
}

// 获取菜单详情
export function getMenuDetail(menuId) {
  return request.get(`/v1/menus/${menuId}`)
}

// 创建菜单
export function createMenu(data) {
  return request.post('/v1/menus', data)
}

// 更新菜单
export function updateMenu(menuId, data) {
  return request.put(`/v1/menus/${menuId}`, data)
}

// 删除菜单
export function deleteMenu(menuId) {
  return request.delete(`/v1/menus/${menuId}`)
}

// 获取当前用户菜单
export function getUserMenus() {
  return request.get('/v1/menus/user-menus')
}

// ==================== 权限管理 ==================== //

// 获取权限列表
export function getPermissionList(params) {
  return request.get('/v1/rbac/permissions/list', { params })
}

// 获取所有权限
export function getAllPermissions() {
  return request.get('/v1/rbac/permissions/all')
}

// 创建权限
export function createPermission(data) {
  return request.post('/v1/rbac/permissions', data)
}

// 更新权限
export function updatePermission(permissionId, data) {
  return request.put(`/v1/rbac/permissions/${permissionId}`, data)
}

// 删除权限
export function deletePermission(permissionId) {
  return request.delete(`/v1/rbac/permissions/${permissionId}`)
}

// ==================== 用户角色管理 ==================== //

// 获取用户角色
export function getUserRoles(userId) {
  return request.get(`/v1/rbac/users/${userId}/roles`)
}

// 设置用户角色
export function setUserRoles(userId, roleIds) {
  return request.post(`/v1/rbac/users/${userId}/roles`, { role_ids: roleIds })
}

// 获取用户权限
export function getUserPermissions(userId) {
  return request.get(`/v1/rbac/users/${userId}/permissions`)
}
