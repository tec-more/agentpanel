import request from '@/utils/request'

// 获取部门列表
export function getDepartmentList(params) {
  return request.get('/v1/departments/list', { params })
}

// 获取部门树形结构
export function getDepartmentTree() {
  return request.get('/v1/departments/tree')
}

// 获取部门详情
export function getDepartmentDetail(deptId) {
  return request.get(`/v1/departments/${deptId}`)
}

// 创建部门
export function createDepartment(data) {
  return request.post('/v1/departments', data)
}

// 更新部门
export function updateDepartment(deptId, data) {
  return request.put(`/v1/departments/${deptId}`, data)
}

// 删除部门
export function deleteDepartment(deptId) {
  return request.delete(`/v1/departments/${deptId}`)
}
