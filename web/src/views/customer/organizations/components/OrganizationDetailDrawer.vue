<template>
  <el-drawer
    :model-value="modelValue"
    :title="detail?.name || '组织详情'"
    size="720px"
    @update:model-value="(val) => emit('update:modelValue', val)"
    @close="handleClose"
  >
    <div v-loading="loading" class="org-detail">
      <el-empty v-if="!loading && !detail" description="组织不存在或加载失败" />

      <template v-else-if="detail">
        <!-- 概要 -->
        <el-descriptions :column="2" border class="summary">
          <el-descriptions-item label="组织 ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="detail.status === 'active' ? 'success' : 'info'" size="small">
              {{ detail.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="所有者">
            {{ detail.owner?.username || '-' }}
            <el-text v-if="detail.owner?.customer_id" size="small" type="info">
              #{{ detail.owner.customer_id }}
            </el-text>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ formatDateTime(detail.created_at) }}
          </el-descriptions-item>
        </el-descriptions>

        <el-tabs v-model="activeTab" class="detail-tabs">
          <!-- 成员 -->
          <el-tab-pane label="成员" name="members">
            <div class="tab-toolbar">
              <el-text type="info">共 {{ members.length }} 名成员</el-text>
              <el-button type="primary" :icon="Plus" size="small" @click="openAddDialog">添加成员</el-button>
            </div>

            <el-table :data="members" border stripe>
              <el-table-column prop="customer_id" label="客户 ID" width="90" align="center" />
              <el-table-column prop="username" label="用户名" min-width="140" />
              <el-table-column label="角色" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="roleTagType(row.role)" size="small">{{ ROLE_MAP[row.role] || row.role }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="加入时间" width="170">
                <template #default="{ row }">
                  {{ formatDateTime(row.joined_at) }}
                </template>
              </el-table-column>
              <el-table-column label="操作" width="90" align="center">
                <template #default="{ row }">
                  <el-button
                    v-if="row.role !== 'owner'"
                    type="danger"
                    link
                    @click="handleRemoveMember(row)"
                  >
                    移除
                  </el-button>
                  <el-text v-else size="small" type="info">不可移除</el-text>
                </template>
              </el-table-column>
              <template #empty>
                <el-empty description="暂无成员" :image-size="80" />
              </template>
            </el-table>
          </el-tab-pane>

          <!-- 授权（只读） -->
          <el-tab-pane label="授权" name="grants">
            <div class="tab-toolbar">
              <el-text type="info">共 {{ grants.length }} 条授权</el-text>
              <el-button type="primary" :icon="Plus" size="small" @click="goCreateGrant">新增授权</el-button>
            </div>
            <el-alert
              type="info"
              :closable="false"
              show-icon
              class="grant-hint"
              title="新增授权请前往资源授权页，主体类型选择「客户组织」后选中本组织"
            />

            <el-table :data="grants" border stripe>
              <el-table-column label="资源" min-width="200">
                <template #default="{ row }">
                  <el-tag size="small" class="type-tag">
                    {{ RESOURCE_TYPE_MAP[row.resource_type] || row.resource_type }}
                  </el-tag>
                  <span>{{ row.resource_name || row.resource_id }}</span>
                </template>
              </el-table-column>
              <el-table-column label="资源状态" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="resourceStatusTagType(row.resource_status)" size="small">
                    {{ RESOURCE_STATUS_MAP[row.resource_status] || row.resource_status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="granted_by" label="授权来源" width="130" show-overflow-tooltip />
              <el-table-column label="授权时间" width="170">
                <template #default="{ row }">
                  {{ formatDateTime(row.created_at) }}
                </template>
              </el-table-column>
              <template #empty>
                <el-empty description="暂无授权" :image-size="80">
                  <el-button type="primary" @click="goCreateGrant">新增授权</el-button>
                </el-empty>
              </template>
            </el-table>
          </el-tab-pane>
        </el-tabs>
      </template>
    </div>

    <!-- 添加成员弹窗 -->
    <el-dialog
      v-model="addDialogVisible"
      title="添加成员"
      width="460px"
      append-to-body
      @close="resetAddForm"
    >
      <el-form :model="addForm" label-width="80px">
        <el-form-item label="选择客户" required>
          <SubjectSelect v-model="addForm.customer_id" subject-type="cus" :multiple="false" />
        </el-form-item>
        <el-form-item label="成员角色" required>
          <el-select v-model="addForm.role" style="width: 100%">
            <el-option label="管理员" value="admin" />
            <el-option label="成员" value="member" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="addLoading" @click="handleAddMember">确定</el-button>
      </template>
    </el-dialog>
  </el-drawer>
</template>

<script setup>
import { ref, computed, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getOrganizationDetail, addOrganizationMember, removeOrganizationMember } from '@/api/organization'
import SubjectSelect from '@/views/grant/components/SubjectSelect.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  orgId: {
    type: [Number, String],
    default: null
  }
})
const emit = defineEmits(['update:modelValue', 'refresh'])

const router = useRouter()

const RESOURCE_TYPE_MAP = {
  model: '模型',
  kb: '知识库',
  tool: '工具',
  agent: '智能体',
  node_type: '节点类型'
}
const RESOURCE_STATUS_MAP = {
  active: '生效中',
  deleted: '已删除',
  inactive: '已停用'
}
const ROLE_MAP = {
  owner: '所有者',
  admin: '管理员',
  member: '成员'
}

const loading = ref(false)
const detail = ref(null)
const activeTab = ref('members')

const addDialogVisible = ref(false)
const addLoading = ref(false)
const addForm = reactive({
  customer_id: '',
  role: 'member'
})

const members = computed(() => detail.value?.members || [])
const grants = computed(() => detail.value?.grants || [])

const fetchDetail = async () => {
  if (!props.orgId) return
  loading.value = true
  detail.value = null
  try {
    const res = await getOrganizationDetail(props.orgId)
    detail.value = res?.data ?? res
  } catch (e) {
    // 错误已由拦截器提示（404 组织不存在）
  } finally {
    loading.value = false
  }
}

const roleTagType = (role) => {
  const map = { owner: 'primary', admin: 'warning', member: 'info' }
  return map[role] || 'info'
}

const resourceStatusTagType = (status) => {
  const map = { active: 'success', deleted: 'danger', inactive: 'warning' }
  return map[status] || 'info'
}

const openAddDialog = () => {
  addDialogVisible.value = true
}

const resetAddForm = () => {
  addForm.customer_id = ''
  addForm.role = 'member'
}

const handleAddMember = async () => {
  if (!addForm.customer_id) {
    ElMessage.warning('请选择客户')
    return
  }
  addLoading.value = true
  try {
    await addOrganizationMember(props.orgId, {
      customer_id: Number(addForm.customer_id),
      role: addForm.role
    })
    ElMessage.success('成员添加成功')
    addDialogVisible.value = false
    resetAddForm()
    await fetchDetail()
    emit('refresh')
  } catch (e) {
    // 错误已由拦截器提示（409 重复成员）
  } finally {
    addLoading.value = false
  }
}

const handleRemoveMember = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确认将「${row.username}」移出该组织？移除后其将立即失去组织授权资源权限。`,
      '移除成员',
      {
        type: 'warning',
        confirmButtonText: '确认移除',
        cancelButtonText: '取消'
      }
    )
    await removeOrganizationMember(props.orgId, row.customer_id)
    ElMessage.success('成员已移除')
    await fetchDetail()
    emit('refresh')
  } catch (e) {
    // 取消或错误（错误已由拦截器提示）
  }
}

const goCreateGrant = () => {
  router.push('/panel/grant')
}

const handleClose = () => {
  detail.value = null
  activeTab.value = 'members'
  addDialogVisible.value = false
  resetAddForm()
}

const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  const date = new Date(dateTime)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 抽屉打开或切换组织时加载详情
watch(
  [() => props.modelValue, () => props.orgId],
  ([visible, id]) => {
    if (visible && id) {
      activeTab.value = 'members'
      fetchDetail()
    }
  }
)
</script>

<style lang="scss" scoped>
.org-detail {
  min-height: 200px;

  .summary {
    margin-bottom: 12px;
  }

  .detail-tabs {
    .tab-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
    }

    .grant-hint {
      margin-bottom: 12px;
    }

    .type-tag {
      margin-right: 6px;
    }
  }
}
</style>
