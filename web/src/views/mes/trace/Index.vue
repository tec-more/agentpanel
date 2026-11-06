<template>
  <div class="production-trace">
    <el-card>
      <template #header>
        <span>生产追溯</span>
      </template>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="正向追溯（原料→成品）" name="forward">
          <el-form :inline="true" :model="forwardForm" class="query-form">
            <el-form-item label="原料批次号" required>
              <el-input v-model="forwardForm.material_batch_no" placeholder="请输入原料批次号" clearable style="width: 300px;" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="doForwardTrace">追溯</el-button>
            </el-form-item>
          </el-form>
          <el-alert v-if="forwardResult.length" :title="`找到 ${forwardResult.length} 条追溯记录`" type="success" :closable="false" style="margin-bottom: 16px;" />
          <el-table :data="forwardResult" border stripe v-loading="forwardLoading">
            <el-table-column prop="trace_type" label="追溯类型" width="100" />
            <el-table-column prop="material_batch_no" label="物料批次号" width="180" />
            <el-table-column prop="material_code" label="物料编码" width="140" />
            <el-table-column prop="material_name" label="物料名称" width="140" />
            <el-table-column prop="wo_code" label="工单编码" width="160" />
            <el-table-column prop="mo_code" label="制造单编码" width="160" />
            <el-table-column prop="process_code" label="工序" width="120" />
            <el-table-column prop="work_center_code" label="工作中心" width="120" />
            <el-table-column prop="operator" label="操作员" width="100" />
            <el-table-column prop="quantity" label="数量" width="80" />
            <el-table-column prop="product_batch_no" label="产出批次号" width="180" />
            <el-table-column prop="created_at" label="时间" width="180" />
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="反向追溯（成品→原料）" name="backward">
          <el-form :inline="true" :model="backwardForm" class="query-form">
            <el-form-item label="成品批次号" required>
              <el-input v-model="backwardForm.product_batch_no" placeholder="请输入成品批次号" clearable style="width: 300px;" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="doBackwardTrace">追溯</el-button>
            </el-form-item>
          </el-form>
          <el-alert v-if="backwardResult.length" :title="`找到 ${backwardResult.length} 条追溯记录`" type="success" :closable="false" style="margin-bottom: 16px;" />
          <el-table :data="backwardResult" border stripe v-loading="backwardLoading">
            <el-table-column prop="trace_type" label="追溯类型" width="100" />
            <el-table-column prop="product_batch_no" label="成品批次号" width="180" />
            <el-table-column prop="material_batch_no" label="物料批次号" width="180" />
            <el-table-column prop="material_code" label="物料编码" width="140" />
            <el-table-column prop="material_name" label="物料名称" width="140" />
            <el-table-column prop="wo_code" label="工单编码" width="160" />
            <el-table-column prop="mo_code" label="制造单编码" width="160" />
            <el-table-column prop="process_code" label="工序" width="120" />
            <el-table-column prop="work_center_code" label="工作中心" width="120" />
            <el-table-column prop="operator" label="操作员" width="100" />
            <el-table-column prop="quantity" label="数量" width="80" />
            <el-table-column prop="created_at" label="时间" width="180" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { forwardTrace, backwardTrace } from '@/api/mes'

const activeTab = ref('forward')
const forwardLoading = ref(false)
const backwardLoading = ref(false)
const forwardResult = ref([])
const backwardResult = ref([])
const forwardForm = ref({ material_batch_no: '' })
const backwardForm = ref({ product_batch_no: '' })

const doForwardTrace = async () => {
  if (!forwardForm.value.material_batch_no) {
    ElMessage.warning('请输入原料批次号')
    return
  }
  forwardLoading.value = true
  try {
    const res = await forwardTrace(forwardForm.value.material_batch_no)
    const d = res.data?.data || res.data || []
    forwardResult.value = Array.isArray(d) ? d : (d.items || [])
  } catch (e) {
    ElMessage.error('正向追溯查询失败')
  }
  forwardLoading.value = false
}

const doBackwardTrace = async () => {
  if (!backwardForm.value.product_batch_no) {
    ElMessage.warning('请输入成品批次号')
    return
  }
  backwardLoading.value = true
  try {
    const res = await backwardTrace(backwardForm.value.product_batch_no)
    const d = res.data?.data || res.data || []
    backwardResult.value = Array.isArray(d) ? d : (d.items || [])
  } catch (e) {
    ElMessage.error('反向追溯查询失败')
  }
  backwardLoading.value = false
}
</script>

<style lang="scss" scoped>
.production-trace {
  .query-form { margin-bottom: 16px; }
}
</style>