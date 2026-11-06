import request from '@/utils/request'

const BASE = '/v1/mes'

export const getMaterialList = (params) => {
  return request.get(`${BASE}/base-data/materials`, { params })
}

export const getMaterialDetail = (id) => {
  return request.get(`${BASE}/base-data/materials/${id}`)
}

export const createMaterial = (data) => {
  return request.post(`${BASE}/base-data/materials`, data)
}

export const updateMaterial = (id, data) => {
  return request.put(`${BASE}/base-data/materials/${id}`, data)
}

export const deleteMaterial = (id) => {
  return request.delete(`${BASE}/base-data/materials/${id}`)
}

export const getBomList = (params) => {
  return request.get(`${BASE}/base-data/boms`, { params })
}

export const getBomDetail = (id) => {
  return request.get(`${BASE}/base-data/boms/${id}`)
}

export const getProductBom = (productId, expandLevel) => {
  const params = expandLevel ? { expand_level: expandLevel } : {}
  return request.get(`${BASE}/base-data/products/${productId}/bom`, { params })
}

export const getProductMrp = (productId, quantity) => {
  const params = quantity ? { quantity } : {}
  return request.get(`${BASE}/base-data/products/${productId}/mrp`, { params })
}

export const createBom = (data) => {
  return request.post(`${BASE}/base-data/boms`, data)
}

export const updateBom = (id, data) => {
  return request.put(`${BASE}/base-data/boms/${id}`, data)
}

export const deleteBom = (id) => {
  return request.delete(`${BASE}/base-data/boms/${id}`)
}

export const getBomVersionList = (params) => {
  return request.get(`${BASE}/base-data/bom-versions`, { params })
}

export const getBomVersionDetail = (id) => {
  return request.get(`${BASE}/base-data/bom-versions/${id}`)
}

export const getBomVersionHistory = (product_code) => {
  return request.get(`${BASE}/base-data/bom-versions/${product_code}/history`)
}

export const createBomVersion = (data) => {
  return request.post(`${BASE}/base-data/bom-versions`, data)
}

export const copyBomVersion = (id, data) => {
  return request.post(`${BASE}/base-data/bom-versions/${id}/copy`, data)
}

export const activateBomVersion = (id) => {
  return request.put(`${BASE}/base-data/bom-versions/${id}/activate`)
}

export const obsoleteBomVersion = (id) => {
  return request.put(`${BASE}/base-data/bom-versions/${id}/obsolete`)
}

export const getBomOptions = () => {
  return request.get(`${BASE}/base-data/boms/options`)
}

export const getWorkcenterList = (params) => {
  return request.get(`${BASE}/base-data/work-centers`, { params })
}

export const getWorkcenterDetail = (id) => {
  return request.get(`${BASE}/base-data/work-centers/${id}`)
}

export const createWorkcenter = (data) => {
  return request.post(`${BASE}/base-data/work-centers`, data)
}

export const updateWorkcenter = (id, data) => {
  return request.put(`${BASE}/base-data/work-centers/${id}`, data)
}

export const deleteWorkcenter = (id) => {
  return request.delete(`${BASE}/base-data/work-centers/${id}`)
}

export const getProcessList = (params) => {
  return request.get(`${BASE}/base-data/processes`, { params })
}

export const getProcessDetail = (id) => {
  return request.get(`${BASE}/base-data/processes/${id}`)
}

export const createProcess = (data) => {
  return request.post(`${BASE}/base-data/processes`, data)
}

export const updateProcess = (id, data) => {
  return request.put(`${BASE}/base-data/processes/${id}`, data)
}

export const deleteProcess = (id) => {
  return request.delete(`${BASE}/base-data/processes/${id}`)
}

export const getRouteList = (params) => {
  return request.get(`${BASE}/base-data/routes`, { params })
}

export const getRouteDetail = (id) => {
  return request.get(`${BASE}/base-data/routes/${id}`)
}

export const createRoute = (data) => {
  return request.post(`${BASE}/base-data/routes`, data)
}

export const updateRoute = (id, data) => {
  return request.put(`${BASE}/base-data/routes/${id}`, data)
}

export const deleteRoute = (id) => {
  return request.delete(`${BASE}/base-data/routes/${id}`)
}

export const getManufacturingOrderList = (params) => {
  return request.get(`${BASE}/production/manufacturing-orders`, { params })
}

export const getManufacturingOrderDetail = (id) => {
  return request.get(`${BASE}/production/manufacturing-orders/${id}`)
}

export const createManufacturingOrder = (data) => {
  return request.post(`${BASE}/production/manufacturing-orders`, data)
}

export const updateManufacturingOrder = (id, data) => {
  return request.put(`${BASE}/production/manufacturing-orders/${id}`, data)
}

export const deleteManufacturingOrder = (id) => {
  return request.delete(`${BASE}/production/manufacturing-orders/${id}`)
}

export const releaseManufacturingOrder = (id) => {
  return request.put(`${BASE}/production/manufacturing-orders/${id}/release`)
}

export const completeManufacturingOrder = (id) => {
  return request.put(`${BASE}/production/manufacturing-orders/${id}/complete`)
}

export const generateWorkOrders = (id, data) => {
  return request.post(`${BASE}/production/manufacturing-orders/${id}/generate-work-orders`, data)
}

export const cancelManufacturingOrder = (id) => {
  return request.put(`${BASE}/production/manufacturing-orders/${id}/cancel`)
}

export const getWorkOrderList = (params) => {
  return request.get(`${BASE}/production/work-orders`, { params })
}

export const getWorkOrderDetail = (id) => {
  return request.get(`${BASE}/production/work-orders/${id}`)
}

export const createWorkOrder = (data) => {
  return request.post(`${BASE}/production/work-orders`, data)
}

export const updateWorkOrder = (id, data) => {
  return request.put(`${BASE}/production/work-orders/${id}`, data)
}

export const deleteWorkOrder = (id) => {
  return request.delete(`${BASE}/production/work-orders/${id}`)
}

export const releaseWorkOrder = (id) => {
  return request.put(`${BASE}/production/work-orders/${id}/release`)
}

export const startWorkOrder = (id, data) => {
  return request.put(`${BASE}/production/work-orders/${id}/start`, data)
}

export const completeWorkOrder = (id, data) => {
  return request.put(`${BASE}/production/work-orders/${id}/complete`, data)
}

export const closeWorkOrder = (id) => {
  return request.put(`${BASE}/production/work-orders/${id}/close`)
}

export const suspendWorkOrder = (id, data) => {
  return request.post(`${BASE}/production/work-orders/${id}/suspend`, data)
}

export const resumeWorkOrder = (id, data) => {
  return request.post(`${BASE}/production/work-orders/${id}/resume`, data)
}

export const submitProductionReport = (data) => {
  return request.post(`${BASE}/production-report`, data)
}

export const batchProductionReport = (data) => {
  return request.post(`${BASE}/production-report/batch`, data)
}

export const getProductionReportList = (params) => {
  return request.get(`${BASE}/production-report`, { params })
}

export const createMaterialRequisition = (data) => {
  return request.post(`${BASE}/material-requisition`, data)
}

export const autoGenerateRequisition = (data) => {
  return request.post(`${BASE}/material-requisition/auto-generate`, data)
}

export const confirmMaterialRequisition = (id) => {
  return request.post(`${BASE}/material-requisition/${id}/confirm`)
}

export const getMaterialRequisitionList = (params) => {
  return request.get(`${BASE}/material-requisition`, { params })
}

export const createMaterialReturn = (data) => {
  return request.post(`${BASE}/material-return`, data)
}

export const confirmMaterialReturn = (id) => {
  return request.post(`${BASE}/material-return/${id}/confirm`)
}

export const getMaterialReturnList = (params) => {
  return request.get(`${BASE}/material-return`, { params })
}

export const createProductionReceipt = (data) => {
  return request.post(`${BASE}/production-receipt`, data)
}

export const confirmProductionReceipt = (id) => {
  return request.post(`${BASE}/production-receipt/${id}/confirm`)
}

export const getProductionReceiptList = (params) => {
  return request.get(`${BASE}/production-receipt`, { params })
}

export const forwardTrace = (materialBatchNo) => {
  return request.get(`${BASE}/trace/forward`, { params: { material_batch_no: materialBatchNo } })
}

export const backwardTrace = (productBatchNo) => {
  return request.get(`${BASE}/trace/backward`, { params: { product_batch_no: productBatchNo } })
}

export const getDashboardOee = (params) => {
  return request.get(`${BASE}/dashboard/oee`, { params })
}

export const getDashboardProduction = (params) => {
  return request.get(`${BASE}/dashboard/production`, { params })
}

export const getDashboardProgress = () => {
  return request.get(`${BASE}/dashboard/progress`)
}

export const generateBarcode = (data) => {
  return request.post(`${BASE}/barcode/generate`, data)
}

export const parseBarcode = (data) => {
  return request.post(`${BASE}/barcode/parse`, data)
}

export const createShift = (data) => {
  return request.post(`${BASE}/shift/definition`, data)
}

export const getShiftList = (params) => {
  return request.get(`${BASE}/shift/definition`, { params })
}

export const createSchedule = (data) => {
  return request.post(`${BASE}/shift/schedule`, data)
}

export const createHandover = (data) => {
  return request.post(`${BASE}/shift/handover`, data)
}

export const reportException = (data) => {
  return request.post(`${BASE}/exception`, data)
}

export const handleException = (id, data) => {
  return request.post(`${BASE}/exception/${id}/handle`, data)
}

export const getExceptionList = (params) => {
  return request.get(`${BASE}/exception`, { params })
}

export const createTooling = (data) => {
  return request.post(`${BASE}/tooling`, data)
}

export const validateTooling = (id) => {
  return request.post(`${BASE}/tooling/${id}/validate`)
}

export const getToolingList = (params) => {
  return request.get(`${BASE}/tooling`, { params })
}

export const recordEnergy = (data) => {
  return request.post(`${BASE}/energy/record`, data)
}

export const getEnergyStatistics = (params) => {
  return request.get(`${BASE}/energy/statistics`, { params })
}
