<template>
  <div class="org-quota-page">
    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filters" @submit.prevent="search">
        <el-form-item label="组织名称">
          <el-input
            v-model="filters.keyword"
            placeholder="输入名称搜索"
            clearable
            style="width: 220px"
            @keyup.enter="search"
          />
        </el-form-item>
        <el-form-item label="组织状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 140px">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="disabled" />
          </el-select>
        </el-form-item>
        <el-form-item label="超期预占">
          <el-select v-model="filters.has_stale_hold" placeholder="全部" clearable style="width: 150px">
            <el-option label="有超期预占" :value="true" />
            <el-option label="无超期预占" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="接近上限">
          <el-switch v-model="filters.near_limit" active-text="≥80%" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <div class="toolbar">
        <div class="toolbar-title">
          组织配额总览
          <el-tag v-if="!canManage" size="small" type="info" class="ml-8">只读</el-tag>
        </div>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </div>

      <el-alert
        v-if="error"
        type="error"
        :closable="false"
        :title="error"
        class="mb-12"
      />

      <el-table v-loading="loading" :data="rows" border stripe>
        <el-table-column label="组织" min-width="170">
          <template #default="{ row }">
            <div class="org-name">{{ row.name }}</div>
            <div class="muted">ID: {{ row.org_id }} · {{ row.member_count }} 名活跃成员</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="套餐" min-width="150">
          <template #default="{ row }">
            <span v-if="row.plan">{{ row.plan_name }} <el-tag size="small" type="info">{{ row.plan }}</el-tag></span>
            <span v-else class="muted">未绑定</span>
          </template>
        </el-table-column>
        <el-table-column label="账户" width="90">
          <template #default="{ row }">
            <el-tag :type="row.account_status === 'active' ? 'success' : 'danger'" size="small">
              {{ row.account_status === 'active' ? '正常' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="额度" width="110" align="right">
          <template #default="{ row }">{{ fmt(row.limit_total) }}</template>
        </el-table-column>
        <el-table-column label="已用" width="110" align="right">
          <template #default="{ row }">{{ fmt(row.used_total) }}</template>
        </el-table-column>
        <el-table-column label="预占" width="130" align="right">
          <template #default="{ row }">
            <span>{{ fmt(row.held_total) }}</span>
            <el-tag v-if="row.has_stale_hold" type="danger" size="small" class="ml-6">
              {{ row.stale_hold_count }} 超期
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="可用" width="110" align="right">
          <template #default="{ row }">{{ fmt(row.available_total) }}</template>
        </el-table-column>
        <el-table-column label="使用率" width="150">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.min(Math.round((row.usage_ratio || 0) * 100), 100)"
              :status="(row.usage_ratio || 0) >= 0.8 ? 'warning' : ''"
              :stroke-width="10"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <template v-if="canManage">
              <el-button link type="primary" @click="openAssign(row)">
                {{ row.plan_id ? '变更套餐' : '分配套餐' }}
              </el-button>
              <el-button v-if="row.plan_id" link type="danger" @click="handleUnbind(row)">解绑</el-button>
              <el-button
                link
                :type="row.account_status === 'active' ? 'danger' : 'success'"
                @click="handleStatus(row)"
              >
                {{ row.account_status === 'active' ? '停用' : '启用' }}
              </el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="load"
          @size-change="search"
        />
      </div>
    </el-card>

    <DetailDrawer v-model="detailVisible" :org-id="detailOrgId" />

    <el-dialog v-model="assignVisible" title="分配/变更组织套餐" width="520px" destroy-on-close>
      <el-form :model="assignForm" label-width="90px">
        <el-form-item label="组织">
          <span>{{ assignOrg?.name }}（ID: {{ assignOrg?.org_id }}）</span>
        </el-form-item>
        <el-form-item label="套餐" required>
          <el-select v-model="assignForm.plan_id" placeholder="选择组织套餐" style="width: 100%">
            <el-option
              v-for="plan in plans"
              :key="plan.id"
              :label="`${plan.name}（${plan.code}）`"
              :value="plan.id"
            >
              <span>{{ plan.name }}</span>
              <span class="plan-meta">{{ planItemsText(plan.quota_items) }}</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="assignForm.priority" :min="0" :max="100" />
          <span class="muted ml-8">数值大者优先，变更会覆盖当前绑定</span>
        </el-form-item>
        <el-alert
          v-if="assignOrg?.plan_id"
          type="warning"
          :closable="false"
          title="该组织已绑定套餐，提交后立即替换，已用额度继续沿用当前账户。"
        />
      </el-form>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="assigning" :disabled="!assignForm.plan_id" @click="submitAssign">
          确认分配
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  assignOrgQuotaPlan,
  getOrgQuotaAvailablePlans,
  getOrgQuotaList,
  unbindOrgQuotaPlan,
  setOrgQuotaStatus
} from '@/api/quota'
import { getMyPermissions } from '@/api/rbac'
import { useUserStore } from '@/stores/user'
import DetailDrawer from './DetailDrawer.vue'

const userStore = useUserStore()

const loading = ref(false)
const error = ref('')
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const permissions = ref([])

const filters = reactive({
  keyword: '',
  status: undefined,
  has_stale_hold: undefined,
  near_limit: false
})

const detailVisible = ref(false)
const detailOrgId = ref(null)

const assignVisible = ref(false)
const assigning = ref(false)
const assignOrg = ref(null)
const plans = ref([])
const assignForm = reactive({ plan_id: undefined, priority: 0 })

const canManage = computed(() => {
  if (userStore.isSuperuser) return true
  return permissions.value.includes('*') || permissions.value.includes('quota:org:manage')
})

function fmt(value) {
  return Number(value || 0).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

function planItemsText(items) {
  if (!items) return ''
  return Object.entries(items).map(([key, val]) => `${key}: ${val}`).join('，')
}

async function loadPermissions() {
  try {
    const res = await getMyPermissions()
    const data = res?.data ?? res
    permissions.value = Array.isArray(data) ? data : []
  } catch (e) {
    permissions.value = []
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      keyword: filters.keyword || undefined,
      status: filters.status || undefined,
      has_stale_hold: filters.has_stale_hold,
      near_limit: filters.near_limit ? true : undefined
    }
    const res = await getOrgQuotaList(params)
    const data = res?.data ?? res
    rows.value = data?.items || []
    total.value = data?.total || 0
  } catch (e) {
    rows.value = []
    total.value = 0
    error.value = e?.response?.data?.detail || e?.message || '加载组织配额失败'
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function reset() {
  filters.keyword = ''
  filters.status = undefined
  filters.has_stale_hold = undefined
  filters.near_limit = false
  search()
}

function openDetail(row) {
  detailOrgId.value = row.org_id
  detailVisible.value = true
}

async function loadPlans() {
  if (plans.value.length) return
  const res = await getOrgQuotaAvailablePlans()
  plans.value = (res?.data ?? res) || []
}

async function openAssign(row) {
  if (row.plan_id) {
    try {
      await ElMessageBox.confirm(
        `组织「${row.name}」已绑定套餐「${row.plan_name}」，继续将替换当前套餐（已用额度沿用）。`,
        '变更套餐确认',
        { type: 'warning', confirmButtonText: '继续变更', cancelButtonText: '取消' }
      )
    } catch (e) {
      return
    }
  }
  assignOrg.value = row
  assignForm.plan_id = row.plan_id || undefined
  assignForm.priority = row.priority || 0
  try {
    await loadPlans()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '套餐列表加载失败')
    return
  }
  assignVisible.value = true
}

async function submitAssign() {
  if (!assignOrg.value?.org_id || !assignForm.plan_id) return
  assigning.value = true
  try {
    await assignOrgQuotaPlan(assignOrg.value.org_id, {
      plan_id: assignForm.plan_id,
      priority: assignForm.priority
    })
    ElMessage.success('套餐分配成功')
    assignVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e?.response?.data?.msg || e?.message || '套餐分配失败')
  } finally {
    assigning.value = false
  }
}

async function handleUnbind(row) {
  try {
    await ElMessageBox.confirm(
      `解绑「${row.plan_name}」后，组织「${row.name}」将立即失去配额，进行中的请求可能被拒绝。`,
      '解绑套餐',
      { type: 'warning', confirmButtonText: '继续解绑', cancelButtonText: '取消' }
    )
    const { value } = await ElMessageBox.prompt(
      `二次确认：请输入组织名称「${row.name}」`,
      '解绑二次确认',
      {
        inputValidator: (val) => val === row.name || '组织名称不一致',
        confirmButtonText: '确认解绑',
        cancelButtonText: '取消'
      }
    )
    if (value !== row.name) return
    await unbindOrgQuotaPlan(row.org_id)
    ElMessage.success('已解绑套餐')
    load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close' && e) {
      ElMessage.error(e?.response?.data?.msg || e?.message || '解绑失败')
    }
  }
}

async function handleStatus(row) {
  const next = row.account_status === 'active' ? 'frozen' : 'active'
  try {
    if (next === 'frozen') {
      await ElMessageBox.confirm(
        `停用后组织「${row.name}」的预占与结算将 fail-closed 拒绝，直到重新启用。`,
        '停用配额账户',
        { type: 'warning', confirmButtonText: '继续停用', cancelButtonText: '取消' }
      )
      const { value } = await ElMessageBox.prompt(
        `二次确认：请输入组织名称「${row.name}」`,
        '停用二次确认',
        {
          inputValidator: (val) => val === row.name || '组织名称不一致',
          confirmButtonText: '确认停用',
          cancelButtonText: '取消'
        }
      )
      if (value !== row.name) return
    } else {
      await ElMessageBox.confirm(
        `确认重新启用组织「${row.name}」的配额账户？`,
        '启用配额账户',
        { type: 'warning', confirmButtonText: '确认启用', cancelButtonText: '取消' }
      )
    }
    await setOrgQuotaStatus(row.org_id, next)
    ElMessage.success(next === 'frozen' ? '账户已停用' : '账户已启用')
    load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close' && e) {
      ElMessage.error(e?.response?.data?.msg || e?.message || '状态更新失败')
    }
  }
}

onMounted(async () => {
  await loadPermissions()
  load()
})
</script>

<style scoped>
.org-quota-page {
  padding: 16px;
}
.filter-card {
  margin-bottom: 12px;
}
.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.toolbar-title {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
}
.org-name {
  font-weight: 500;
}
.muted {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.mb-12 { margin-bottom: 12px; }
.ml-6 { margin-left: 6px; }
.ml-8 { margin-left: 8px; }
.plan-meta {
  float: right;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-left: 12px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
