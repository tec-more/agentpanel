<template>
  <div class="material-flow">
    <el-card>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="领料单" name="requisition">
          <div style="margin-bottom: 16px;">
            <el-button type="primary" @click="showReqDialog = true">创建领料单</el-button>
            <el-button @click="autoGenerateReq">根据BOM自动生成</el-button>
          </div>
          <el-table :data="reqData" border stripe v-loading="reqLoading">
            <el-table-column prop="requisition_code" label="领料单号" width="180" />
            <el-table-column prop="mo_code" label="制造单编码" width="160" />
            <el-table-column prop="requisition_type" label="类型" width="100" />
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column prop="applicant" label="申请人" width="100" />
            <el-table-column prop="created_at" label="创建时间" width="180" />
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button v-if="row.status === 'draft'" type="primary" size="small" @click="confirmReq(row.id)">确认</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="退料单" name="return">
          <el-button type="primary" style="margin-bottom: 16px;" @click="showRetDialog = true">创建退料单</el-button>
          <el-table :data="retData" border stripe v-loading="retLoading">
            <el-table-column prop="return_code" label="退料单号" width="180" />
            <el-table-column prop="mo_code" label="制造单编码" width="160" />
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column prop="operator" label="操作员" width="100" />
            <el-table-column prop="created_at" label="创建时间" width="180" />
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button v-if="row.status === 'draft'" type="primary" size="small" @click="confirmRet(row.id)">确认</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="完工入库" name="receipt">
          <el-button type="primary" style="margin-bottom: 16px;" @click="showRcptDialog = true">创建入库单</el-button>
          <el-table :data="rcptData" border stripe v-loading="rcptLoading">
            <el-table-column prop="receipt_code" label="入库单号" width="180" />
            <el-table-column prop="mo_code" label="制造单编码" width="160" />
            <el-table-column prop="product_name" label="产品" width="120" />
            <el-table-column prop="batch_no" label="批次号" width="180" />
            <el-table-column prop="quantity" label="数量" width="80" />
            <el-table-column prop="inspection_result" label="检验结果" width="100" />
            <el-table-column prop="status" label="状态" width="100" />
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button v-if="row.status === 'draft'" type="primary" size="small" @click="confirmRcpt(row.id)">确认</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="showReqDialog" title="创建领料单" width="500px">
      <el-form :model="reqForm" label-width="100px">
        <el-form-item label="制造单编码" required><el-input v-model="reqForm.mo_code" /></el-form-item>
        <el-form-item label="仓库编码" required><el-input v-model="reqForm.warehouse_code" /></el-form-item>
        <el-form-item label="库位编码" required><el-input v-model="reqForm.location_code" /></el-form-item>
        <el-form-item label="申请人" required><el-input v-model="reqForm.applicant" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showReqDialog = false">取消</el-button>
        <el-button type="primary" @click="createReq">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showRcptDialog" title="创建入库单" width="500px">
      <el-form :model="rcptForm" label-width="100px">
        <el-form-item label="制造单编码" required><el-input v-model="rcptForm.mo_code" /></el-form-item>
        <el-form-item label="产品编码" required><el-input v-model="rcptForm.product_code" /></el-form-item>
        <el-form-item label="产品名称" required><el-input v-model="rcptForm.product_name" /></el-form-item>
        <el-form-item label="数量" required><el-input-number v-model="rcptForm.quantity" :min="1" /></el-form-item>
        <el-form-item label="仓库编码" required><el-input v-model="rcptForm.warehouse_code" /></el-form-item>
        <el-form-item label="检验结果" required>
          <el-select v-model="rcptForm.inspection_result">
            <el-option label="合格" value="qualified" />
            <el-option label="让步接收" value="concession" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRcptDialog = false">取消</el-button>
        <el-button type="primary" @click="createRcpt">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getMaterialRequisitionList, createMaterialRequisition, confirmMaterialRequisition,
  autoGenerateRequisition, getMaterialReturnList, confirmMaterialReturn,
  getProductionReceiptList, createProductionReceipt, confirmProductionReceipt
} from '@/api/mes'

const activeTab = ref('requisition')
const reqLoading = ref(false)
const retLoading = ref(false)
const rcptLoading = ref(false)
const reqData = ref([])
const retData = ref([])
const rcptData = ref([])
const showReqDialog = ref(false)
const showRcptDialog = ref(false)

const reqForm = ref({ mo_code: '', warehouse_code: 'WH001', location_code: 'LOC001', applicant: '' })
const rcptForm = ref({ mo_code: '', product_code: '', product_name: '', quantity: 1, warehouse_code: 'WH001', location_code: 'LOC001', inspection_result: 'qualified' })

const fetchReq = async () => {
  reqLoading.value = true
  try {
    const res = await getMaterialRequisitionList({ page: 1, page_size: 50 })
    reqData.value = res.data?.data?.items || res.data?.items || []
  } catch (e) { ElMessage.error('获取领料单失败') }
  reqLoading.value = false
}

const fetchRet = async () => {
  retLoading.value = true
  try {
    const res = await getMaterialReturnList({ page: 1, page_size: 50 })
    retData.value = res.data?.data?.items || res.data?.items || []
  } catch (e) { ElMessage.error('获取退料单失败') }
  retLoading.value = false
}

const fetchRcpt = async () => {
  rcptLoading.value = true
  try {
    const res = await getProductionReceiptList({ page: 1, page_size: 50 })
    rcptData.value = res.data?.data?.items || res.data?.items || []
  } catch (e) { ElMessage.error('获取入库单失败') }
  rcptLoading.value = false
}

const createReq = async () => {
  try {
    await createMaterialRequisition({ ...reqForm.value, requisition_type: 'manual', details: [] })
    ElMessage.success('领料单创建成功')
    showReqDialog.value = false
    fetchReq()
  } catch (e) { ElMessage.error('创建失败') }
}

const autoGenerateReq = async () => {
  const mo_code = prompt('请输入制造单编码')
  if (!mo_code) return
  try {
    await autoGenerateRequisition({ mo_code })
    ElMessage.success('领料单自动生成成功')
    fetchReq()
  } catch (e) { ElMessage.error('自动生成失败') }
}

const confirmReq = async (id) => {
  try { await confirmMaterialRequisition(id); ElMessage.success('确认成功'); fetchReq() }
  catch (e) { ElMessage.error('确认失败') }
}

const confirmRet = async (id) => {
  try { await confirmMaterialReturn(id); ElMessage.success('确认成功'); fetchRet() }
  catch (e) { ElMessage.error('确认失败') }
}

const createRcpt = async () => {
  try {
    await createProductionReceipt({ ...rcptForm.value, unit: '个' })
    ElMessage.success('入库单创建成功')
    showRcptDialog.value = false
    fetchRcpt()
  } catch (e) { ElMessage.error('创建失败') }
}

const confirmRcpt = async (id) => {
  try { await confirmProductionReceipt(id); ElMessage.success('确认成功'); fetchRcpt() }
  catch (e) { ElMessage.error('确认失败') }
}

watch(activeTab, (v) => {
  if (v === 'requisition') fetchReq()
  else if (v === 'return') fetchRet()
  else if (v === 'receipt') fetchRcpt()
})

onMounted(fetchReq)
</script>