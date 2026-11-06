<template>
  <div class="crm-config">
    <el-tabs v-model="activeTab" type="border-card">
      <el-tab-pane label="商机阶段" name="stages">
        <div class="tab-header">
          <el-button type="primary" :icon="Plus" size="small" @click="openStageDialog()">新增阶段</el-button>
        </div>
        <el-table v-loading="loading.stages" :data="stages" border stripe>
          <el-table-column prop="sort_order" label="排序" width="80" align="center" />
          <el-table-column prop="name" label="阶段名称" min-width="120" />
          <el-table-column prop="code" label="编码" min-width="160" />
          <el-table-column prop="probability" label="概率(%)" width="100" align="center" />
          <el-table-column label="赢单阶段" width="100" align="center">
            <template #default="{ row }"><el-tag v-if="row.is_won_stage" type="success" size="small">是</el-tag></template>
          </el-table-column>
          <el-table-column label="输单阶段" width="100" align="center">
            <template #default="{ row }"><el-tag v-if="row.is_lost_stage" type="danger" size="small">是</el-tag></template>
          </el-table-column>
          <el-table-column label="启用" width="80" align="center">
            <template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '是' : '否' }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" width="160" align="center">
            <template #default="{ row }">
              <el-button type="primary" link :icon="Edit" size="small" @click="openStageDialog(row)">编辑</el-button>
              <el-button type="danger" link :icon="Delete" size="small" @click="deleteStageItem(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="线索来源" name="sources">
        <div class="tab-header">
          <el-button type="primary" :icon="Plus" size="small" @click="openSourceDialog()">新增来源</el-button>
        </div>
        <el-table v-loading="loading.sources" :data="sources" border stripe>
          <el-table-column prop="sort_order" label="排序" width="80" align="center" />
          <el-table-column prop="name" label="来源名称" min-width="140" />
          <el-table-column prop="code" label="编码" min-width="140" />
          <el-table-column label="启用" width="80" align="center">
            <template #default="{ row }"><el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '是' : '否' }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" width="160" align="center">
            <template #default="{ row }">
              <el-button type="primary" link :icon="Edit" size="small" @click="openSourceDialog(row)">编辑</el-button>
              <el-button type="danger" link :icon="Delete" size="small" @click="deleteSourceItem(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="系统设置" name="settings">
        <el-form :model="settings" label-width="140px" style="max-width: 500px; margin-top: 16px">
          <el-form-item label="自动回收天数">
            <el-input-number v-model="settings.auto_recycle_days" :min="1" style="width: 100%" />
            <div class="form-tip">超过该天数未跟进的线索将自动回收</div>
          </el-form-item>
          <el-form-item label="超期预警天数">
            <el-input-number v-model="settings.stale_warning_days" :min="1" style="width: 100%" />
            <div class="form-tip">超过该天数未跟进的线索将标记为超期</div>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="submitting" @click="saveSettings">保存设置</el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="stageDialogVisible" :title="stageForm.id ? '编辑阶段' : '新增阶段'" width="480px">
      <el-form :model="stageForm" label-width="100px">
        <el-form-item label="阶段名称">
          <el-input v-model="stageForm.name" />
        </el-form-item>
        <el-form-item v-if="!stageForm.id" label="编码">
          <el-input v-model="stageForm.code" placeholder="英文编码" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="stageForm.sort_order" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="概率(%)">
          <el-input-number v-model="stageForm.probability" :min="0" :max="100" style="width: 100%" />
        </el-form-item>
        <el-form-item label="赢单阶段">
          <el-switch v-model="stageForm.is_won_stage" />
        </el-form-item>
        <el-form-item label="输单阶段">
          <el-switch v-model="stageForm.is_lost_stage" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="stageForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stageDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveStage">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="sourceDialogVisible" :title="sourceForm.id ? '编辑来源' : '新增来源'" width="480px">
      <el-form :model="sourceForm" label-width="100px">
        <el-form-item label="来源名称">
          <el-input v-model="sourceForm.name" />
        </el-form-item>
        <el-form-item v-if="!sourceForm.id" label="编码">
          <el-input v-model="sourceForm.code" placeholder="英文编码" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="sourceForm.sort_order" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="sourceForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sourceDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveSource">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete } from '@element-plus/icons-vue'
import {
  getStages, saveStage as createStage, updateStage, deleteStage,
  getLeadSources, saveLeadSource, updateLeadSource, deleteLeadSource,
  getSettings, updateSettings
} from '@/api/crm'

const activeTab = ref('stages')
const submitting = ref(false)
const loading = reactive({ stages: false, sources: false })
const stages = ref([])
const sources = ref([])
const settings = reactive({ auto_recycle_days: 30, stale_warning_days: 14 })

const stageDialogVisible = ref(false)
const sourceDialogVisible = ref(false)

const stageForm = reactive({ id: null, name: '', code: '', sort_order: 0, probability: null, is_won_stage: false, is_lost_stage: false, is_active: true })
const sourceForm = reactive({ id: null, name: '', code: '', sort_order: 0, is_active: true })

const fetchStages = async () => {
  loading.stages = true
  try { stages.value = await getStages().then(r => r.data) || [] }
  catch (e) { console.error('获取阶段失败:', e) }
  finally { loading.stages = false }
}

const fetchSources = async () => {
  loading.sources = true
  try { sources.value = await getLeadSources().then(r => r.data) || [] }
  catch (e) { console.error('获取来源失败:', e) }
  finally { loading.sources = false }
}

const fetchSettings = async () => {
  try {
    const res = await getSettings()
    Object.assign(settings, res.data)
  } catch (e) { console.error('获取设置失败:', e) }
}

const openStageDialog = (row) => {
  if (row) { Object.assign(stageForm, row) }
  else { Object.assign(stageForm, { id: null, name: '', code: '', sort_order: 0, probability: null, is_won_stage: false, is_lost_stage: false, is_active: true }) }
  stageDialogVisible.value = true
}

const saveStage = async () => {
  if (!stageForm.name.trim()) { ElMessage.warning('请输入阶段名称'); return }
  submitting.value = true
  try {
    if (stageForm.id) { await updateStage(stageForm.id, stageForm); ElMessage.success('更新成功') }
    else {
      if (!stageForm.code.trim()) { ElMessage.warning('请输入编码'); submitting.value = false; return }
      await createStage(stageForm); ElMessage.success('创建成功')
    }
    stageDialogVisible.value = false; fetchStages()
  } catch (e) { ElMessage.error(e.message || '操作失败') }
  finally { submitting.value = false }
}

const deleteStageItem = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除阶段 "${row.name}" 吗？`, '提示', { type: 'warning' })
    await deleteStage(row.id); ElMessage.success('删除成功'); fetchStages()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

const openSourceDialog = (row) => {
  if (row) { Object.assign(sourceForm, row) }
  else { Object.assign(sourceForm, { id: null, name: '', code: '', sort_order: 0, is_active: true }) }
  sourceDialogVisible.value = true
}

const saveSource = async () => {
  if (!sourceForm.name.trim()) { ElMessage.warning('请输入来源名称'); return }
  submitting.value = true
  try {
    if (sourceForm.id) { await updateLeadSource(sourceForm.id, sourceForm); ElMessage.success('更新成功') }
    else {
      if (!sourceForm.code.trim()) { ElMessage.warning('请输入编码'); submitting.value = false; return }
      await saveLeadSource(sourceForm); ElMessage.success('创建成功')
    }
    sourceDialogVisible.value = false; fetchSources()
  } catch (e) { ElMessage.error(e.message || '操作失败') }
  finally { submitting.value = false }
}

const deleteSourceItem = async (row) => {
  try {
    await ElMessageBox.confirm(`确定删除来源 "${row.name}" 吗？`, '提示', { type: 'warning' })
    await deleteLeadSource(row.id); ElMessage.success('删除成功'); fetchSources()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

const saveSettings = async () => {
  submitting.value = true
  try {
    await updateSettings(settings)
    ElMessage.success('保存成功')
  } catch (e) { ElMessage.error(e.message || '保存失败') }
  finally { submitting.value = false }
}

onMounted(() => { fetchStages(); fetchSources(); fetchSettings() })
</script>

<style lang="scss" scoped>
.crm-config {
  .tab-header { margin-bottom: 16px; }
  .form-tip { font-size: 12px; color: #909399; margin-top: 4px; }
}
</style>
