<template>
  <div class="flow-rule">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>审批流程规则</span>
          <el-button type="primary" @click="openDialog('create')">新建流程规则</el-button>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        class="tip-alert"
        title="流程即审批规则。配置了业务模型与拦截方法后，对应的业务操作（如创建采购订单）将自动被拦截并要求先提交审批。"
      />

      <el-table v-loading="loading" :data="tableData" border stripe class="table-margin">
        <el-table-column prop="name" label="流程名称" min-width="150" />
        <el-table-column prop="code" label="流程编码" width="160" />
        <el-table-column prop="model" label="业务模型" width="150" show-overflow-tooltip />
        <el-table-column prop="action" label="执行动作" width="90">
          <template #default="{ row }">{{ row.action || '全部' }}</template>
        </el-table-column>
        <el-table-column prop="methods" label="拦截方法" width="140">
          <template #default="{ row }">
            <el-tag v-for="m in (row.methods || [])" :key="m" size="small" class="method-tag">{{ m }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="80" align="center" />
        <el-table-column prop="route_patterns" label="路由模式" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.route_patterns && row.route_patterns.length">
              {{ row.route_patterns.join('，') }}
            </span>
            <span v-else class="empty-text">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="business_type" label="业务类型" width="120">
          <template #default="{ row }">{{ row.business_type || '通用' }}</template>
        </el-table-column>
        <el-table-column prop="is_system" label="系统预设" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_system ? 'warning' : 'info'" size="small">
              {{ row.is_system ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.is_active"
              @change="(val) => handleToggleStatus(row, val)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openDialog('edit', row)">编辑</el-button>
            <el-button
              v-if="!row.is_system"
              type="danger" link @click="handleDelete(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.page_size"
          :page-sizes="[10, 20, 50]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>

    <!-- 设计器对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="1280px"
      top="4vh"
      destroy-on-close
      class="flow-designer-dialog"
    >
      <el-form :model="formData" label-width="96px" ref="formRef">
        <div class="base-grid">
          <el-form-item label="流程名称" prop="name">
            <el-input v-model="formData.name" placeholder="请输入流程名称" />
          </el-form-item>
          <el-form-item label="流程编码" prop="code">
            <el-input
              v-model="formData.code"
              placeholder="请输入流程编码（唯一）"
              :disabled="Boolean(formData.id)"
            />
          </el-form-item>
          <el-form-item label="业务模型">
            <el-select
              v-model="formData.model"
              placeholder="选择业务模型"
              filterable
              style="width: 100%"
              @change="onModelChange"
            >
              <el-option v-for="m in modelOptions" :key="m.model" :label="m.label" :value="m.model" />
            </el-select>
            <div class="form-tip">业务模型来自插件 models 目录，格式：中文(英文标识)</div>
          </el-form-item>
          <el-form-item label="执行动作">
            <el-select
              v-model="formData.action"
              placeholder="选择执行动作"
              clearable
              filterable
              style="width: 100%"
              :disabled="!formData.model"
            >
              <el-option v-for="a in actionOptions" :key="a.value" :label="a.label" :value="a.value" />
            </el-select>
            <div class="form-tip">该模型对应 service 的公开方法；不填表示匹配全部动作（创建/更新/删除）</div>
          </el-form-item>
          <el-form-item label="拦截方法">
            <el-checkbox-group v-model="formData.methods">
              <el-checkbox value="POST" label="POST" />
              <el-checkbox value="PUT" label="PUT" />
              <el-checkbox value="DELETE" label="DELETE" />
            </el-checkbox-group>
          </el-form-item>
          <el-form-item label="优先级">
            <el-input-number v-model="formData.priority" :min="0" :max="999" />
            <div class="form-tip">数字越大优先级越高；同一模型+动作命中多条流程时取最高</div>
          </el-form-item>
          <el-form-item label="前端路由">
            <div class="route-patterns-input">
              <el-tag
                v-for="(pat, idx) in formData.route_patterns"
                :key="idx"
                closable
                size="small"
                class="route-tag"
                @close="removeRoutePattern(idx)"
              >
                {{ pat }}
              </el-tag>
              <el-input
                v-if="routeInputVisible"
                ref="routeInputRef"
                v-model="routeInputValue"
                size="small"
                class="route-input"
                placeholder="如 /panel/purchase/order/:id"
                @keyup.enter="confirmRoutePattern"
                @blur="confirmRoutePattern"
              />
              <el-button v-else size="small" class="route-add-btn" @click="showRouteInput">
                + 添加路由
              </el-button>
            </div>
            <div class="form-tip">匹配的页面路由，含 :id 表示详情页；全局审批组件据此自动显示。如 /panel/purchase/order 和 /panel/purchase/order/:id</div>
          </el-form-item>
          <el-form-item label="业务类型">
            <el-input v-model="formData.business_type" placeholder="如：purchase_order, expense" />
          </el-form-item>
          <el-form-item label="是否启用">
            <el-switch v-model="formData.is_active" />
          </el-form-item>
        </div>
        <el-form-item label="流程描述">
          <el-input v-model="formData.description" type="textarea" :rows="2" />
        </el-form-item>

        <el-divider>流程节点设计（拖拽连线，右侧配置审批方式）</el-divider>
        <ApprovalFlowCanvas ref="canvasRef" />
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">保存流程规则</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getFlowList, createFlow, updateFlow, deleteFlow, toggleFlowStatus, validateFlow,
  getAvailableModels, getModelActions
} from '@/api/approval'
import ApprovalFlowCanvas from '@/components/approval/ApprovalFlowCanvas.vue'

const loading = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('')
const dialogMode = ref('create')
const canvasRef = ref()

const modelOptions = ref([])
const actionOptions = ref([])

const pagination = reactive({ page: 1, page_size: 10, total: 0 })
const formData = reactive({
  id: null,
  name: '',
  code: '',
  business_type: '',
  model: '',
  action: '',
  methods: ['POST', 'PUT', 'DELETE'],
  priority: 0,
  route_patterns: [],
  description: '',
  is_active: true,
  form_config: [],
  flow_config: {}
})

// 前端路由 tag 输入
const routeInputVisible = ref(false)
const routeInputValue = ref('')
const routeInputRef = ref(null)

const showRouteInput = () => {
  routeInputVisible.value = true
  nextTick(() => {
    routeInputRef.value?.focus?.()
  })
}

const confirmRoutePattern = () => {
  const val = routeInputValue.value.trim()
  if (val && !formData.route_patterns.includes(val)) {
    formData.route_patterns.push(val)
  }
  routeInputVisible.value = false
  routeInputValue.value = ''
}

const removeRoutePattern = (idx) => {
  formData.route_patterns.splice(idx, 1)
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getFlowList(pagination)
    if (res.code === 0 || res.code === 200 || res.success) {
      tableData.value = res.data.items || []
      pagination.total = res.data.total || 0
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

const fetchModels = async () => {
  try {
    const res = await getAvailableModels()
    if (res.code === 0 || res.code === 200 || res.success) {
      modelOptions.value = res.data || []
    }
  } catch (e) {
    console.error(e)
  }
}

const fetchActions = async (model) => {
  try {
    const res = await getModelActions(model)
    if (res.code === 0 || res.code === 200 || res.success) {
      actionOptions.value = res.data || []
    }
  } catch (e) {
    console.error(e)
  }
}

const resetForm = () => {
  Object.assign(formData, {
    id: null, name: '', code: '', business_type: '', model: '', action: '',
    methods: ['POST', 'PUT', 'DELETE'], priority: 0, route_patterns: [],
    description: '', is_active: true,
    form_config: [], flow_config: {}
  })
  actionOptions.value = []
  routeInputVisible.value = false
  routeInputValue.value = ''
}

const onModelChange = async (val) => {
  formData.action = ''
  if (val) {
    await fetchActions(val)
  } else {
    actionOptions.value = []
  }
}

const openDialog = (mode, row) => {
  resetForm()
  dialogMode.value = mode
  dialogTitle.value = mode === 'create' ? '新建流程规则' : '编辑流程规则'
  if (row) {
    Object.assign(formData, {
      id: row.id, name: row.name, code: row.code, business_type: row.business_type || '',
      model: row.model || '', action: row.action || '', methods: row.methods || ['POST', 'PUT', 'DELETE'],
      priority: row.priority || 0, route_patterns: row.route_patterns || [],
      description: row.description || '', is_active: row.is_active,
      form_config: row.form_config || [], flow_config: row.flow_config || {}
    })
    if (row.model) {
      fetchActions(row.model)
    }
  }
  dialogVisible.value = true
  nextTick(() => {
    canvasRef.value?.load(mode === 'edit' ? (row?.flow_config || {}) : null)
  })
}

const handleToggleStatus = async (row, val) => {
  try {
    await toggleFlowStatus(row.id, val)
    ElMessage.success('状态已更新')
  } catch (e) {
    row.is_active = !val
    console.error(e)
  }
}

const submitForm = async () => {
  let flowConfig = {}
  try {
    flowConfig = canvasRef.value?.serialize() || {}
  } catch (e) {
    ElMessage.error('读取流程设计失败')
    return
  }
  if (!flowConfig.nodes || !flowConfig.nodes.length) {
    ElMessage.error('请至少添加一个流程节点')
    return
  }
  formData.flow_config = flowConfig

  // 前端预校验
  try {
    const vres = await validateFlow({ ...formData })
    const data = vres?.data || vres
    if (data && data.valid === false) {
      ElMessage.error('流程配置有误：' + (data.errors || []).join('；'))
      return
    }
  } catch (e) {
    // 校验接口异常不阻断保存，交由 create/update 兜底
  }

  try {
    let res
    if (dialogMode.value === 'create') {
      const { id, ...createData } = formData
      res = await createFlow(createData)
    } else {
      const { id, ...updateData } = formData
      res = await updateFlow(id, updateData)
    }
    if (res.code === 0 || res.code === 200 || res.success) {
      ElMessage.success('保存成功')
      dialogVisible.value = false
      fetchData()
    } else {
      ElMessage.error(res.msg || '保存失败')
    }
  } catch (e) {
    console.error(e)
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除流程规则「${row.name}」吗？`, '提示', { type: 'warning' })
    const res = await deleteFlow(row.id)
    if (res.code === 0 || res.code === 200 || res.success) {
      ElMessage.success('删除成功')
      fetchData()
    }
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

onMounted(() => {
  fetchData()
  fetchModels()
})
</script>

<style scoped lang="scss">
.flow-rule { padding: 16px; }

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tip-alert {
  margin-bottom: 16px;
}

.table-margin {
  margin-top: 8px;
}

.base-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 24px;
}

.method-tag {
  margin-right: 4px;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
  margin-top: 4px;
}

.route-patterns-input {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  width: 100%;

  .route-tag {
    margin: 0;
  }

  .route-input {
    width: 220px;
  }

  .route-add-btn {
    border-style: dashed;
  }
}

.empty-text {
  color: #c0c4cc;
}

.pagination-wrapper {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

:deep(.flow-designer-dialog) {
  .el-dialog__body { padding-top: 12px; }
}
</style>
