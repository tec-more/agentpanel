import request from '@/utils/request'

// 获取产品列表
export const getProductList = (params) => {
  return request.get('/v1/product/list', { params })
}

// 获取产品详情
export const getProductDetail = (id) => {
  return request.get(`/v1/product/item/${id}`)
}

// 创建产品
export const createProduct = (data) => {
  return request.post('/v1/product', data)
}

// 更新产品
export const updateProduct = (id, data) => {
  return request.put(`/v1/product/item/${id}`, data)
}

// 删除产品
export const deleteProduct = (id) => {
  return request.delete(`/v1/product/item/${id}`)
}

// 批量删除产品
export const batchDeleteProduct = (ids) => {
  return request.delete('/v1/product/batch', { data: { ids } })
}

// 更新产品库存
export const updateProductStock = (id, data) => {
  return request.patch(`/v1/product/item/${id}/stock`, data)
}

// 上下架产品
export const toggleProductStatus = (id) => {
  return request.patch(`/v1/product/item/${id}/toggle-status`)
}

// 获取可关联的成品物料列表
export const getAvailableMaterials = (params) => {
  return request.get('/v1/product/materials/available', { params })
}

// 获取产品分类列表
export const getCategoryList = (params) => {
  return request.get('/v1/product/categories', { params })
}

// 获取产品分类选项
export const getCategoryOptions = () => {
  return request.get('/v1/product/categories/options')
}

// 获取分类详情
export const getCategoryDetail = (id) => {
  return request.get(`/v1/product/categories/${id}`)
}

// 创建分类
export const createCategory = (data) => {
  return request.post('/v1/product/categories', data)
}

// 更新分类
export const updateCategory = (id, data) => {
  return request.put(`/v1/product/categories/${id}`, data)
}

// 删除分类
export const deleteCategory = (id) => {
  return request.delete(`/v1/product/categories/${id}`)
}

export const getAttributeList = (params) => {
  return request.get('/v1/product/attributes', { params })
}

export const getAttributeOptions = (params) => {
  return request.get('/v1/product/attributes/options', { params })
}

export const getAttributeDetail = (id) => {
  return request.get(`/v1/product/attributes/${id}`)
}

export const createAttribute = (data) => {
  return request.post('/v1/product/attributes', data)
}

export const updateAttribute = (id, data) => {
  return request.put(`/v1/product/attributes/${id}`, data)
}

export const deleteAttribute = (id) => {
  return request.delete(`/v1/product/attributes/${id}`)
}

export const getAttributeValues = (id) => {
  return request.get(`/v1/product/attributes/${id}/values`)
}

export const createAttributeValue = (data) => {
  return request.post('/v1/product/attributes/values', data)
}

export const updateAttributeValue = (id, data) => {
  return request.put(`/v1/product/attributes/values/${id}`, data)
}

export const deleteAttributeValue = (id) => {
  return request.delete(`/v1/product/attributes/values/${id}`)
}

export const getMaterialVariantList = (params) => {
  return request.get('/v1/product/material-variants', { params })
}

export const getMaterialVariantDetail = (id) => {
  return request.get(`/v1/product/material-variants/${id}`)
}

export const createMaterialVariant = (data) => {
  return request.post('/v1/product/material-variants', data)
}

export const updateMaterialVariant = (id, data) => {
  return request.put(`/v1/product/material-variants/${id}`, data)
}

export const deleteMaterialVariant = (id) => {
  return request.delete(`/v1/product/material-variants/${id}`)
}

export const getProductVariantList = (params) => {
  return request.get('/v1/product/variants', { params })
}

export const getProductVariantDetail = (id) => {
  return request.get(`/v1/product/variants/${id}`)
}

export const createProductVariant = (data) => {
  return request.post('/v1/product/variants', data)
}

export const updateProductVariant = (id, data) => {
  return request.put(`/v1/product/variants/${id}`, data)
}

export const deleteProductVariant = (id) => {
  return request.delete(`/v1/product/variants/${id}`)
}