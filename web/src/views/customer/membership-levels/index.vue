<template>
  <div class="membership-levels-container">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>会员等级配置</span>
          <el-button type="primary" @click="handleCreate">
            <el-icon><Plus /></el-icon>
            新增等级
          </el-button>
        </div>
      </template>

      <!-- 筛选区 -->
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="等级名称">
          <el-input v-model="searchForm.name" placeholder="请输入等级名称" clearable />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.is_active" placeholder="请选择状态" clearable>
            <el-option label="全部" :value="null" />
            <el-option label="启用" :value="true" />
            <el-option label="禁用" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="fetchData">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="handleReset">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 数据表格 -->
      <el-table :data="tableData" style="width: 100%" v-loading="loading" border>
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="name" label="等级名称" width="140" />
        <el-table-column prop="level_type" label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getLevelTypeColor(row.level_type)" size="small">
              {{ getLevelTypeName(row.level_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="duration_days" label="有效期" width="100" align="center">
          <template #default="{ row }">
            <span v-if="row.duration_days > 0" style="color: #409EFF;">{{ row.duration_days }}天</span>
            <span v-else style="color: #67C23A;">无限期</span>
          </template>
        </el-table-column>
        <el-table-column prop="hours" label="包含小时数" width="120" align="center">
          <template #default="{ row }">
            <div style="color: #409EFF; font-weight: bold; font-size: 16px;">
              {{ row.hours }} 小时
            </div>
            <div style="font-size: 11px; color: #909399;">
              充值时长
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="购买价格" width="120" align="center">
          <template #default="{ row }">
            <div style="color: #F56C6C; font-weight: bold; font-size: 16px;">
              ¥{{ row.price }}
            </div>
            <div style="font-size: 11px; color: #909399;">
              会员费
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="discount_percentage" label="充值折扣" width="120" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.discount_percentage > 0" type="danger" effect="plain" size="small">
              {{ row.discount_percentage }}% OFF
            </el-tag>
            <span v-else style="color: #909399; font-size: 12px;">无折扣</span>
          </template>
        </el-table-column>
        <el-table-column prop="features" label="特权" width="250" align="center">
          <template #default="{ row }">
            <el-tag
              v-for="(feature, index) in (row.features || []).slice(0, 3)"
              :key="index"
              size="small"
              style="margin: 2px;"
            >
              {{ feature }}
            </el-tag>
            <el-tooltip v-if="row.features && row.features.length > 3" :content="row.features.join(', ')">
              <el-tag size="small" type="info" style="margin: 2px;">
                +{{ row.features.length - 3 }}
              </el-tag>
            </el-tooltip>
            <span v-if="!row.features || row.features.length === 0" style="color: #909399; font-size: 12px;">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column prop="is_active" label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="handleEdit(row)">
              编辑
            </el-button>
            <el-button
              :type="row.is_active ? 'warning' : 'success'"
              size="small"
              @click="handleToggleStatus(row)"
            >
              {{ row.is_active ? '禁用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="pagination.total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="fetchData"
        @current-change="fetchData"
      />
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="700px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="120px">
        <el-form-item label="等级类型" prop="level_type">
          <el-select v-model="form.level_type" placeholder="请选择等级类型" style="width: 100%;" :disabled="isEdit">
            <el-option label="普通会员 (regular)" value="regular">
              <div>
                <span style="font-weight: bold;">普通会员</span>
                <span style="color: #909399; font-size: 12px; margin-left: 8px;">注册即拥有，无限期，无折扣</span>
              </div>
            </el-option>
            <el-option label="VIP会员 (vip)" value="vip">
              <div>
                <span style="font-weight: bold;">VIP会员</span>
                <span style="color: #F56C6C; font-size: 12px; margin-left: 8px;">付费会员，365天有效期，充值9折</span>
              </div>
            </el-option>
            <el-option label="SVIP会员 (svip)" value="svip">
              <div>
                <span style="font-weight: bold;">SVIP会员</span>
                <span style="color: #FFC107; font-size: 12px; margin-left: 8px;">超级会员，365天有效期，充值8折</span>
              </div>
            </el-option>
          </el-select>
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            {{ form.level_type === 'regular' ? '默认等级，注册用户自动拥有' : '付费等级，购买后享受充值折扣' }}
          </div>
        </el-form-item>

        <el-form-item label="等级名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入等级名称，如：VIP会员" />
        </el-form-item>

        <el-form-item label="购买价格" prop="price">
          <el-input-number v-model="form.price" :min="0" :precision="2" placeholder="请输入会员购买价格" style="width: 100%;" :disabled="form.level_type === 'regular'" />
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            {{ form.level_type === 'regular' ? '普通会员免费' : '购买此会员需要支付的价格' }}
          </div>
        </el-form-item>

        <el-form-item label="有效期天数" prop="duration_days">
          <el-input-number v-model="form.duration_days" :min="0" placeholder="请输入有效期天数" style="width: 100%;" :disabled="form.level_type === 'regular'" />
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            <span v-if="form.level_type === 'regular'" style="color: #67C23A;">普通会员无限期</span>
            <span v-else>会员有效期（天数），建议365天</span>
          </div>
        </el-form-item>

        <el-form-item label="包含小时数" prop="hours">
          <el-input-number v-model="form.hours" :min="0" placeholder="套餐包含的小时数" style="width: 100%;" />
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            <span v-if="form.level_type === 'regular'" style="color: #909399;">普通会员默认0小时</span>
            <span v-else-if="form.hours > 0" style="color: #409EFF;">购买套餐可获得 {{ form.hours }} 小时充值时长</span>
            <span v-else style="color: #909399;">设置套餐包含的充值小时数</span>
          </div>
        </el-form-item>

        <el-form-item label="充值折扣" prop="discount_percentage">
          <el-input-number
            v-model="form.discount_percentage"
            :min="0"
            :max="100"
            placeholder="充值折扣百分比"
            style="width: 100%;"
            :disabled="form.level_type === 'regular'"
          />
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            <span v-if="form.level_type === 'regular'" style="color: #909399;">普通会员无折扣</span>
            <span v-else-if="form.discount_percentage > 0" style="color: #F56C6C;">购买充值包可享受 {{ form.discount_percentage }}% 折扣</span>
            <span v-else style="color: #909399;">设置充值折扣百分比（0表示无折扣）</span>
          </div>
        </el-form-item>

        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="请输入等级描述（选填）" />
        </el-form-item>

        <el-form-item label="特权列表" prop="features">
          <el-select
            v-model="form.features"
            multiple
            filterable
            allow-create
            placeholder="输入特权后按回车添加，或从下拉选择"
            style="width: 100%;"
          >
            <el-option label="基础功能" value="基础功能" />
            <el-option label="正常使用" value="正常使用" />
            <el-option label="优先客服" value="优先客服" />
            <el-option label="专属客服" value="专属客服" />
            <el-option label="充值9折" value="充值9折" />
            <el-option label="充值8折" value="充值8折" />
            <el-option label="无限翻译" value="无限翻译" />
            <el-option label="API访问" value="API访问" />
            <el-option label="批量翻译" value="批量翻译" />
            <el-option label="离线翻译" value="离线翻译" />
            <el-option label="多语言互译" value="多语言互译" />
          </el-select>
          <div style="font-size: 12px; color: #909399; margin-top: 4px;">
            已选择 {{ form.features?.length || 0 }} 项特权
          </div>
        </el-form-item>

        <el-form-item label="状态" prop="is_active">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="禁用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh } from '@element-plus/icons-vue'
import { getMembershipLevels, createMembershipLevel, updateMembershipLevel, deleteMembershipLevel } from '@/api/customer'

// 响应式数据
const loading = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增等级')
const formRef = ref()

const searchForm = reactive({
  name: '',
  is_active: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const form = reactive({
  id: null,
  level_type: 'regular',
  name: '',
  description: '',
  duration_days: 0,
  hours: 0,
  price: 0,
  discount_percentage: 0,
  features: [],
  is_active: true
})

const rules = {
  level_type: [{ required: true, message: '请选择等级类型', trigger: 'change' }],
  name: [{ required: true, message: '请输入等级名称', trigger: 'blur' }],
  price: [{ required: true, message: '请输入购买价格', trigger: 'blur' }],
  duration_days: [{ required: true, message: '请输入有效期天数', trigger: 'blur' }]
}

// 方法
const fetchData = async () => {
  loading.value = true
  try {
    const res = await getMembershipLevels({
      page: pagination.page,
      page_size: pagination.pageSize,
      name: searchForm.name || undefined,
      is_active: searchForm.is_active
    })
    tableData.value = res.data.items || res.data || []
    pagination.total = res.data.total || 0
  } catch (e) {
    ElMessage.error('获取数据失败')
  } finally {
    loading.value = false
  }
}

const handleReset = () => {
  searchForm.name = ''
  searchForm.is_active = null
  fetchData()
}

const handleCreate = () => {
  dialogTitle.value = '新增会员等级'
  Object.assign(form, {
    id: null,
    level_type: 'regular',
    name: '',
    description: '',
    duration_days: 0,
    hours: 0,
    price: 0,
    discount_percentage: 0,
    features: [],
    is_active: true
  })
  dialogVisible.value = true
}

const handleEdit = (row) => {
  dialogTitle.value = '编辑等级'
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleSubmit = async () => {
  await formRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      if (form.id) {
        await updateMembershipLevel(form.id, form)
        ElMessage.success('更新成功')
      } else {
        await createMembershipLevel(form)
        ElMessage.success('创建成功')
      }
      dialogVisible.value = false
      fetchData()
    } catch (e) {
      ElMessage.error('操作失败')
    }
  })
}

const handleToggleStatus = async (row) => {
  try {
    await updateMembershipLevel(row.id, { is_active: !row.is_active })
    ElMessage.success('状态切换成功')
    fetchData()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const handleDelete = (row) => {
  ElMessageBox.confirm('确定要删除该等级吗？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    try {
      await deleteMembershipLevel(row.id)
      ElMessage.success('删除成功')
      fetchData()
    } catch (e) {
      ElMessage.error('删除失败')
    }
  })
}

const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN')
}

// 获取等级类型中文名
const getLevelTypeName = (type) => {
  const typeMap = {
    'regular': '普通',
    'vip': 'VIP',
    'svip': 'SVIP'
  }
  return typeMap[type] || type
}

// 获取等级类型颜色
const getLevelTypeColor = (type) => {
  const colorMap = {
    'regular': 'info',
    'vip': 'danger',
    'svip': 'warning'
  }
  return colorMap[type] || ''
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.membership-levels-container {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-form {
  margin-bottom: 20px;
}
</style>


