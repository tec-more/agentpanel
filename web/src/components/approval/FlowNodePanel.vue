<template>
  <div class="flow-node-panel" v-if="target">
    <!-- 审批节点 -->
    <template v-if="kind === 'node' && nodeType === 'approve'">
      <div class="panel-title">
        <el-icon><Stamp /></el-icon><span>审批节点配置</span>
      </div>

      <el-form label-width="92px" size="default">
        <el-form-item label="节点名称">
          <el-input v-model="target.data.name" placeholder="如：部门经理审批" />
        </el-form-item>

        <el-form-item label="审批人数">
          <div class="mode-grid">
            <div
              v-for="m in approveModes"
              :key="m.value"
              class="mode-card"
              :class="{ active: target.data.approve_type === m.value }"
              @click="setMode(m.value)"
            >
              <div class="mode-name">{{ m.label }}</div>
              <div class="mode-desc">{{ m.desc }}</div>
            </div>
          </div>
        </el-form-item>

        <el-form-item label="审批人来源">
          <div class="mode-grid">
            <div
              v-for="s in approverSources"
              :key="s.value"
              class="mode-card"
              :class="{ active: target.data.approver_config?.type === s.value }"
              @click="setSource(s.value)"
            >
              <div class="mode-name">{{ s.label }}</div>
              <div class="mode-desc">{{ s.desc }}</div>
            </div>
          </div>
        </el-form-item>

        <!-- 指定用户 -->
        <el-form-item v-if="target.data.approver_config?.type === 'user'" label="选择用户">
          <el-select
            v-model="target.data.approver_config.user_ids"
            multiple
            filterable
            collapse-tags
            placeholder="勾选审批人（支持多人）"
            style="width: 100%"
            @visible-change="(v) => v && loadUsers()"
          >
            <el-option v-for="u in userOptions" :key="u.value" :label="u.label" :value="u.value" />
          </el-select>
          <div class="hint">{{ (target.data.approver_config.user_ids || []).length }} 人</div>
        </el-form-item>

        <!-- 按角色 -->
        <el-form-item v-if="target.data.approver_config?.type === 'role'" label="选择角色">
          <el-select
            v-model="target.data.approver_config.role_ids"
            multiple
            filterable
            collapse-tags
            placeholder="勾选角色（角色下所有成员）"
            style="width: 100%"
            @visible-change="(v) => v && loadRoles()"
          >
            <el-option v-for="r in roleOptions" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>

        <!-- 部门主管 -->
        <template v-if="target.data.approver_config?.type === 'dept_head'">
          <el-form-item label="取申请人部门">
            <el-switch v-model="useApplicantDept" @change="onDeptSwitch" />
            <span class="hint">开启则自动取申请人所在部门负责人</span>
          </el-form-item>
          <el-form-item v-if="!useApplicantDept" label="指定部门">
            <el-select
              v-model="target.data.approver_config.dept_id"
              filterable
              placeholder="选择部门"
              style="width: 100%"
              @visible-change="(v) => v && loadDepts()"
            >
              <el-option v-for="d in deptOptions" :key="d.value" :label="d.label" :value="d.value" />
            </el-select>
          </el-form-item>
        </template>
      </el-form>
    </template>

    <!-- 条件节点 -->
    <template v-else-if="kind === 'node' && nodeType === 'condition'">
      <div class="panel-title">
        <el-icon><Share /></el-icon><span>条件节点配置</span>
      </div>
      <el-form label-width="92px" size="default">
        <el-form-item label="节点名称">
          <el-input v-model="target.data.name" placeholder="如：金额判断" />
        </el-form-item>
        <el-form-item label="字段">
          <el-input v-model="target.data.field" placeholder="如：amount" />
        </el-form-item>
        <el-form-item label="运算符">
          <el-select v-model="target.data.operator" style="width: 100%">
            <el-option v-for="op in operators" :key="op.value" :label="op.label" :value="op.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="比较值">
          <el-input v-model="target.data.value" placeholder="如：10000" />
        </el-form-item>
        <div class="hint">从该节点引出的每条连线代表一个分支，满足条件走对应分支，可设一条「默认分支」。</div>
      </el-form>
    </template>

    <!-- 开始/结束节点 -->
    <template v-else-if="kind === 'node' && (nodeType === 'start' || nodeType === 'end')">
      <div class="panel-title">
        <el-icon><CircleCheck /></el-icon><span>{{ nodeType === 'start' ? '开始节点' : '结束节点' }}</span>
      </div>
      <el-form label-width="92px" size="default">
        <el-form-item label="节点名称">
          <el-input v-model="target.data.name" />
        </el-form-item>
        <div class="hint">{{ nodeType === 'start' ? '流程发起入口，无需额外配置。' : '流程终点，审批在此结束。' }}</div>
      </el-form>
    </template>

    <!-- 连线 -->
    <template v-else-if="kind === 'edge'">
      <div class="panel-title">
        <el-icon><Connection /></el-icon><span>连线 / 动作分支</span>
      </div>
      <el-form label-width="92px" size="default">
        <el-form-item label="分支走向">
          <el-radio-group v-model="edgeAction">
            <el-radio-button value="approve">通过</el-radio-button>
            <el-radio-button value="reject">拒绝</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- 条件节点引出的边：配置条件 -->
        <template v-if="sourceNodeType === 'condition'">
          <el-form-item label="默认分支">
            <el-switch v-model="edgeIsDefault" />
            <span class="hint">开启后作为不满足任何条件时的默认走向</span>
          </el-form-item>
          <template v-if="!edgeIsDefault">
            <el-form-item label="字段">
              <el-input v-model="condField" placeholder="如：amount" />
            </el-form-item>
            <el-form-item label="运算符">
              <el-select v-model="condOperator" style="width: 100%">
                <el-option v-for="op in operators" :key="op.value" :label="op.label" :value="op.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="比较值">
              <el-input v-model="condValue" placeholder="如：10000" />
            </el-form-item>
          </template>
        </template>

        <div class="hint">
          连线：<b>{{ sourceName }}</b> → <b>{{ targetName }}</b>
        </div>
      </el-form>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  APPROVE_MODES, APPROVER_SOURCES, CONDITION_OPERATORS
} from './flowNodeMeta'
import { getUserList } from '@/api/user'
import { getRoleList } from '@/api/rbac'
import { getDepartmentList } from '@/api/department'

const props = defineProps({
  target: { type: Object, default: null },
  kind: { type: String, default: 'node' },        // node | edge
  sourceNodeType: { type: String, default: '' },    // 对 edge 有效
  sourceName: { type: String, default: '' },
  targetName: { type: String, default: '' }
})

const approveModes = APPROVE_MODES
const approverSources = APPROVER_SOURCES
const operators = CONDITION_OPERATORS

const nodeType = computed(() => props.target?.data?.nodeType || props.sourceNodeType)

// ---------- 审批模式 / 来源 ----------
function setMode(val) {
  props.target.data.approve_type = val
}
function setSource(val) {
  const cfg = props.target.data.approver_config || {}
  if (val === 'user') cfg.user_ids = cfg.user_ids || []
  if (val === 'role') cfg.role_ids = cfg.role_ids || []
  if (val === 'dept_head') {
    cfg.use_applicant_dept = cfg.use_applicant_dept ?? true
    cfg.dept_id = cfg.dept_id ?? null
  }
  cfg.type = val
  props.target.data.approver_config = { ...cfg }
}

// ---------- 部门主管开关 ----------
const useApplicantDept = computed({
  get: () => props.target?.data?.approver_config?.use_applicant_dept !== false,
  set: (v) => { if (props.target?.data?.approver_config) props.target.data.approver_config.use_applicant_dept = v }
})
function onDeptSwitch(v) {
  if (props.target?.data?.approver_config) {
    props.target.data.approver_config.use_applicant_dept = v
    if (v) props.target.data.approver_config.dept_id = null
  }
}

// ---------- 连线动作 / 条件 ----------
const edgeAction = computed({
  get: () => props.target?.data?.action || 'approve',
  set: (v) => { if (props.target) props.target.data = { ...(props.target.data || {}), action: v } }
})
const edgeIsDefault = computed({
  get: () => props.target?.data?.isDefault || false,
  set: (v) => { if (props.target) props.target.data = { ...(props.target.data || {}), isDefault: v } }
})
const condField = computed({
  get: () => props.target?.data?.condition?.field || '',
  set: (v) => updateCondition('field', v)
})
const condOperator = computed({
  get: () => props.target?.data?.condition?.operator || '>',
  set: (v) => updateCondition('operator', v)
})
const condValue = computed({
  get: () => props.target?.data?.condition?.value ?? '',
  set: (v) => updateCondition('value', v)
})
function updateCondition(key, val) {
  const cur = props.target?.data?.condition || {}
  const next = { ...cur, [key]: val }
  props.target.data = { ...(props.target.data || {}), condition: next, isDefault: false }
}

// ---------- 数据源 ----------
const userOptions = ref([])
const roleOptions = ref([])
const deptOptions = ref([])

function extractList(res) {
  const d = res && (res.data || res)
  if (Array.isArray(d)) return d
  if (d && Array.isArray(d.items)) return d.items
  if (d && Array.isArray(d.list)) return d.list
  return []
}
async function loadUsers() {
  if (userOptions.value.length) return
  try {
    const res = await getUserList({ page: 1, page_size: 200 })
    userOptions.value = extractList(res).map(u => ({
      label: u.alias || u.username || u.name || u.id,
      value: u.id
    }))
  } catch (e) { ElMessage.error('加载用户列表失败') }
}
async function loadRoles() {
  if (roleOptions.value.length) return
  try {
    const res = await getRoleList({ page: 1, page_size: 200 })
    roleOptions.value = extractList(res).map(r => ({
      label: r.name || r.role_name || r.id,
      value: r.id
    }))
  } catch (e) { ElMessage.error('加载角色列表失败') }
}
async function loadDepts() {
  if (deptOptions.value.length) return
  try {
    const res = await getDepartmentList({ page: 1, page_size: 200 })
    deptOptions.value = extractList(res).map(d => ({
      label: d.name || d.dept_name || d.id,
      value: d.id
    }))
  } catch (e) { ElMessage.error('加载部门列表失败') }
}

// 面板切换时按需预拉取
watch(() => props.target, (t) => {
  if (!t) return
  const type = t.data?.approver_config?.type
  if (type === 'user') loadUsers()
  if (type === 'role') loadRoles()
  if (type === 'dept_head') loadDepts()
}, { immediate: true })
</script>

<style scoped lang="scss">
.flow-node-panel {
  padding: 4px 2px;
}
.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 16px;
  .el-icon { color: #2563eb; }
}
.mode-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
}
.mode-card {
  flex: 1 1 calc(50% - 8px);
  min-width: 120px;
  border: 1.5px solid #e5e7eb;
  border-radius: 10px;
  padding: 8px 10px;
  cursor: pointer;
  transition: all .2s ease;
  background: #fff;
  &:hover { border-color: #93c5fd; box-shadow: 0 4px 12px rgba(37,99,235,.12); }
  &.active {
    border-color: #2563eb;
    background: linear-gradient(135deg, #eff6ff, #dbeafe);
    box-shadow: 0 4px 14px rgba(37,99,235,.18);
  }
  .mode-name { font-weight: 600; font-size: 13px; color: #1f2937; }
  .mode-desc { font-size: 11px; color: #6b7280; margin-top: 2px; line-height: 1.3; }
}
.hint {
  font-size: 12px;
  color: #6b7280;
  margin: 4px 0 0 2px;
  line-height: 1.5;
}
</style>
