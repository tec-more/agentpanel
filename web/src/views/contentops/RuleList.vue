<template>
  <div class="contentops-rules">
    <el-card shadow="never">
      <el-tabs v-model="activeTab">
        <!-- ===== 合规规则 ===== -->
        <el-tab-pane label="合规规则" name="rules">
          <template #header>
            <div class="tab-toolbar">
              <el-select v-model="layerFilter" placeholder="全部层级" clearable style="width: 150px"
                         @change="fetchRules">
                <el-option label="L1 法律法规" value="L1" />
                <el-option label="L2 行业" value="L2" />
                <el-option label="L3 平台" value="L3" />
                <el-option label="L4 品牌" value="L4" />
              </el-select>
              <el-button type="primary" :icon="Plus" @click="handleCreateRule">新建规则</el-button>
            </div>
          </template>

          <el-table v-loading="ruleLoading" :data="rules" border stripe>
            <el-table-column prop="id" label="ID" width="70" align="center" />
            <el-table-column label="层级" width="110" align="center">
              <template #default="{ row }">
                <el-tag :type="layerType(row.layer)" size="small">{{ row.layer }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="风险" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="riskType(row.risk_level)" size="small">{{ row.risk_level }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="type" label="类型" width="100" align="center" />
            <el-table-column prop="pattern" label="规则表达式" min-width="200" show-overflow-tooltip />
            <el-table-column label="动作" width="90" align="center">
              <template #default="{ row }">{{ actionLabel(row.action) }}</template>
            </el-table-column>
            <el-table-column label="来源" width="100" align="center">
              <template #default="{ row }">{{ row.source || '-' }}</template>
            </el-table-column>
            <el-table-column label="启用" width="80" align="center">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
                  {{ row.enabled ? '是' : '否' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right" align="center">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleEditRule(row)">编辑</el-button>
                <el-button type="danger" link size="small" @click="handleDeleteRule(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- ===== 平台适配配置 ===== -->
        <el-tab-pane label="平台适配配置" name="platform">
          <div class="platform-toolbar">
            <el-select v-model="platformFilter" placeholder="选择平台" style="width: 180px"
                       @change="fetchPlatformRules">
              <el-option v-for="p in PLATFORMS" :key="p.value" :label="p.label" :value="p.value" />
            </el-select>
            <el-button type="primary" :icon="Plus" @click="handleAddPlatformRule">新增配置</el-button>
          </div>
          <el-table v-loading="platformLoading" :data="platformRules" border stripe>
            <el-table-column prop="key" label="配置键" min-width="180" />
            <el-table-column label="配置值" min-width="280">
              <template #default="{ row }">
                <code>{{ JSON.stringify(row.value) }}</code>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="140" align="center">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="handleEditPlatformRule(row)">编辑</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 合规规则弹窗 -->
    <el-dialog v-model="ruleDialog" :title="editingRuleId ? '编辑规则' : '新建规则'" width="620px"
               destroy-on-close>
      <el-form :model="ruleForm" label-width="90px">
        <el-form-item label="规则层">
          <el-select v-model="ruleForm.layer" style="width:100%">
            <el-option label="L1 法律法规" value="L1" />
            <el-option label="L2 行业" value="L2" />
            <el-option label="L3 平台" value="L3" />
            <el-option label="L4 品牌" value="L4" />
          </el-select>
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="类型">
              <el-select v-model="ruleForm.type" style="width:100%">
                <el-option label="关键词" value="keyword" />
                <el-option label="正则" value="regex" />
                <el-option label="语义" value="semantic" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="风险等级">
              <el-select v-model="ruleForm.risk_level" style="width:100%">
                <el-option label="P0 高危" value="P0" />
                <el-option label="P1 中危" value="P1" />
                <el-option label="P2 低危" value="P2" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="规则表达式" required>
          <el-input v-model="ruleForm.pattern" placeholder="关键词或正则表达式" />
        </el-form-item>
        <el-form-item label="动作">
          <el-select v-model="ruleForm.action" style="width:100%">
            <el-option label="硬拦截 block" value="block" />
            <el-option label="人工放行 warn" value="warn" />
            <el-option label="提示 hint" value="hint" />
          </el-select>
        </el-form-item>
        <el-form-item label="依据条款">
          <el-input v-model="ruleForm.basis" />
        </el-form-item>
        <el-form-item label="替换建议">
          <el-input v-model="ruleForm.suggestion" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="ruleForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ruleDialog = false">取消</el-button>
        <el-button type="primary" @click="submitRule">保存</el-button>
      </template>
    </el-dialog>

    <!-- 平台配置弹窗 -->
    <el-dialog v-model="platformDialog" :title="editingPlatformKey ? '编辑配置' : '新增配置'" width="560px">
      <el-form label-width="90px">
        <el-form-item label="配置键">
          <el-input v-model="platformKey" :disabled="!!editingPlatformKey"
                    placeholder="如 title_max / cover_ratio" />
        </el-form-item>
        <el-form-item label="配置值(JSON)">
          <el-input v-model="platformValue" type="textarea" :rows="6" placeholder='如 {"max": 80, "min": 6}' />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="platformDialog = false">取消</el-button>
        <el-button type="primary" @click="submitPlatformRule">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import {
  getRuleList, createRule, updateRule, deleteRule,
  getPlatformRules, setPlatformRule, PLATFORMS
} from '@/api/contentops'

const JSON = window.JSON

const activeTab = ref('rules')
const ruleLoading = ref(false)
const rules = ref([])
const layerFilter = ref(null)
const ruleDialog = ref(false)
const editingRuleId = ref(null)
const ruleForm = reactive({
  layer: 'L1', type: 'keyword', pattern: '', risk_level: 'P1',
  action: 'warn', basis: '', suggestion: '', enabled: true
})

const platformLoading = ref(false)
const platformFilter = ref('wechat')
const platformRules = ref([])
const platformDialog = ref(false)
const editingPlatformKey = ref(null)
const platformKey = ref('')
const platformValue = ref('{}')

function layerType(l) { return ({ L1: 'danger', L2: 'warning', L3: 'primary', L4: 'success' })[l] || 'info' }
function riskType(r) { return ({ P0: 'danger', P1: 'warning', P2: 'info' })[r] || 'info' }
function actionLabel(a) { return ({ block: '硬拦截', warn: '人工放行', hint: '提示' })[a] || a }

async function fetchRules() {
  ruleLoading.value = true
  try {
    const { data } = await getRuleList(layerFilter.value ? { layer: layerFilter.value } : {})
    rules.value = data.items || []
  } finally { ruleLoading.value = false }
}
function handleCreateRule() {
  editingRuleId.value = null
  Object.assign(ruleForm, {
    layer: 'L1', type: 'keyword', pattern: '', risk_level: 'P1',
    action: 'warn', basis: '', suggestion: '', enabled: true
  })
  ruleDialog.value = true
}
function handleEditRule(row) {
  editingRuleId.value = row.id
  Object.assign(ruleForm, {
    layer: row.layer, type: row.type, pattern: row.pattern, risk_level: row.risk_level,
    action: row.action, basis: row.basis || '', suggestion: row.suggestion || '', enabled: row.enabled
  })
  ruleDialog.value = true
}
async function submitRule() {
  if (!ruleForm.pattern) { ElMessage.warning('规则表达式必填'); return }
  const payload = { ...ruleForm }
  if (editingRuleId.value) await updateRule(editingRuleId.value, payload)
  else await createRule(payload)
  ElMessage.success('已保存')
  ruleDialog.value = false
  fetchRules()
}
async function handleDeleteRule(row) {
  await ElMessageBox.confirm(`确认删除规则「${row.pattern}」？`, '提示', { type: 'warning' })
  await deleteRule(row.id)
  ElMessage.success('已删除')
  fetchRules()
}

async function fetchPlatformRules() {
  if (!platformFilter.value) { platformRules.value = []; return }
  platformLoading.value = true
  try {
    const { data } = await getPlatformRules(platformFilter.value)
    platformRules.value = data.items || []
  } finally { platformLoading.value = false }
}
function handleAddPlatformRule() {
  editingPlatformKey.value = null
  platformKey.value = ''
  platformValue.value = '{}'
  platformDialog.value = true
}
function handleEditPlatformRule(row) {
  editingPlatformKey.value = row.key
  platformKey.value = row.key
  platformValue.value = JSON.stringify(row.value, null, 2)
  platformDialog.value = true
}
async function submitPlatformRule() {
  let value
  try { value = JSON.parse(platformValue.value) }
  catch (_) { ElMessage.error('配置值不是合法 JSON'); return }
  await setPlatformRule(platformFilter.value, platformKey.value, value)
  ElMessage.success('已保存')
  platformDialog.value = false
  fetchPlatformRules()
}

onMounted(() => { fetchRules(); fetchPlatformRules() })
</script>

<style scoped>
.tab-toolbar, .platform-toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; }
code { font-size: 12px; }
</style>
