<template>
  <div class="menu-management">
    <!-- 操作栏 -->
    <el-card shadow="never" class="action-card">
      <div class="action-bar">
        <el-button type="primary" :icon="Plus" @click="handleAdd">新增菜单</el-button>
        <el-button :icon="Sort" @click="toggleExpandAll">
          {{ isExpandAll ? '折叠全部' : '展开全部' }}
        </el-button>
      </div>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never" class="table-card">
      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="tableData"
        border
        row-key="id"
        :tree-props="{ children: 'children', hasChildren: 'hasChildren' }"
        :default-expand-all="isExpandAll"
      >
        <el-table-column prop="name" label="菜单名称" min-width="180" />
        <el-table-column prop="icon" label="图标" width="80" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.icon" :size="18">
              <component :is="normalizeIcon(row.icon)" />
            </el-icon>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getMenuTypeTag(row.menu_type)" size="small">
              {{ getMenuTypeName(row.menu_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="path" label="路由路径" min-width="150" show-overflow-tooltip />
        <el-table-column prop="component" label="组件路径" min-width="150" show-overflow-tooltip />
        <el-table-column prop="permission" label="权限标识" min-width="120" show-overflow-tooltip />
        <el-table-column prop="sort" label="排序" width="120" align="center">
          <template #default="{ row }">
            <div class="sort-actions">
              <el-button
                type="primary"
                link
                :icon="Top"
                size="small"
                title="上移"
                @click="handleMoveUp(row)"
              />
              <span class="sort-value">{{ row.sort }}</span>
              <el-button
                type="primary"
                link
                :icon="Bottom"
                size="small"
                title="下移"
                @click="handleMoveDown(row)"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_visible ? 'success' : 'info'" size="small">
              {{ row.is_visible ? '显示' : '隐藏' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              v-if="row.menu_type !== 'button'"
              type="primary"
              link
              :icon="Plus"
              @click="handleAddChild(row)"
            >
              添加
            </el-button>
            <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">编辑</el-button>
            <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="650px"
      @close="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="24">
            <el-form-item label="上级菜单">
              <el-tree-select
                v-model="form.parent_id"
                :data="menuTreeOptions"
                :props="{ label: 'name', value: 'id', children: 'children' }"
                placeholder="请选择上级菜单"
                clearable
                check-strictly
                :render-after-expand="false"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>

          <el-col :span="24">
            <el-form-item label="菜单类型" prop="menu_type">
              <el-radio-group v-model="form.menu_type">
                <el-radio value="directory">目录</el-radio>
                <el-radio value="menu">菜单</el-radio>
                <el-radio value="button">按钮</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>

          <el-col :span="12">
            <el-form-item label="菜单名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入菜单名称" />
            </el-form-item>
          </el-col>

          <el-col :span="12" v-if="form.menu_type !== 'button'">
            <el-form-item label="菜单图标">
              <el-select v-model="form.icon" placeholder="请选择图标" filterable clearable style="width: 100%">
                <el-option v-for="icon in iconOptions" :key="icon" :label="icon" :value="icon">
                  <el-icon style="margin-right: 8px"><component :is="icon" /></el-icon>
                  <span>{{ icon }}</span>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :span="12" v-if="form.menu_type !== 'button'">
            <el-form-item label="路由路径" prop="path">
              <el-input v-model="form.path" placeholder="请输入路由路径" />
            </el-form-item>
          </el-col>

          <el-col :span="12" v-if="form.menu_type === 'menu'">
            <el-form-item label="组件路径" prop="component">
              <el-input v-model="form.component" placeholder="请输入组件路径" />
            </el-form-item>
          </el-col>

          <el-col :span="12" v-if="form.menu_type !== 'directory'">
            <el-form-item label="权限标识" prop="permission">
              <el-input v-model="form.permission" placeholder="如: user:list" />
            </el-form-item>
          </el-col>

          <el-col :span="12">
            <el-form-item label="排序" prop="sort">
              <el-input-number v-model="form.sort" :min="0" :max="999" style="width: 100%" />
            </el-form-item>
          </el-col>

          <el-col :span="12" v-if="form.menu_type !== 'button'">
            <el-form-item label="是否显示">
              <el-radio-group v-model="form.is_visible">
                <el-radio :value="true">显示</el-radio>
                <el-radio :value="false">隐藏</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>

          <el-col :span="12" v-if="form.menu_type !== 'button'">
            <el-form-item label="是否缓存">
              <el-radio-group v-model="form.is_cached">
                <el-radio :value="true">缓存</el-radio>
                <el-radio :value="false">不缓存</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Sort, Top, Bottom } from '@element-plus/icons-vue'
import { getMenuTree, createMenu, updateMenu, deleteMenu } from '@/api/rbac'
import { useMenuStore } from '@/stores/menu'

const menuStore = useMenuStore()
// 规范化图标名（兼容历史 Lucide 风格名称），用于表格渲染
const normalizeIcon = (name) => menuStore.getIconName(name)

const loading = ref(false)
const submitLoading = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const isExpandAll = ref(true)
const formRef = ref(null)
const tableRef = ref(null)

const tableData = ref([])
const flatMenuList = ref([]) // 扁平化的菜单列表，用于排序
const menuTreeOptions = ref([])

// 常用图标列表（均为 @element-plus/icons-vue 官方图标名，按业务分组）
const iconOptions = [
  // 通用 / 系统
  'Odometer', 'Setting', 'Menu', 'HomeFilled', 'House', 'Operation', 'Management', 'Platform',
  'User', 'UserFilled', 'Avatar', 'OfficeBuilding', 'Key', 'Lock', 'Tools',
  'Document', 'DocumentChecked', 'Folder', 'FolderOpened', 'Files', 'Notebook', 'Reading', 'Tickets', 'Stamp',
  'List', 'Grid', 'Collection',
  // 数据 / 图表
  'DataAnalysis', 'DataLine', 'DataBoard', 'PieChart', 'TrendCharts', 'Histogram', 'Rank',
  // 商品 / 销售 / 客户 / CRM
  'Goods', 'Box', 'ShoppingCart', 'ShoppingBag', 'Sell', 'Shop', 'Suitcase', 'Briefcase',
  'Money', 'Wallet', 'Coin', 'CreditCard', 'PriceTag', 'Discount', 'Present',
  // 消息 / 沟通
  'Message', 'Bell', 'BellFilled', 'Notification', 'ChatDotRound', 'ChatLineRound', 'ChatRound', 'Promotion', 'Headset', 'Service',
  // AI / 智能体
  'Cpu', 'Monitor', 'Guide', 'Compass',
  // 基础操作
  'Calendar', 'Clock', 'Search', 'Edit', 'EditPen', 'Delete', 'Plus', 'Minus', 'Check', 'Close',
  'Refresh', 'Sort', 'Upload', 'Download', 'Link', 'Share', 'Picture', 'Camera', 'VideoCamera', 'Location', 'Phone'
]

const form = ref({
  parent_id: null,
  menu_type: 'menu',
  name: '',
  icon: '',
  path: '',
  component: '',
  permission: '',
  sort: 0,
  is_visible: true,
  is_cached: true
})

const rules = {
  name: [{ required: true, message: '请输入菜单名称', trigger: 'blur' }],
  menu_type: [{ required: true, message: '请选择菜单类型', trigger: 'change' }]
}

const dialogTitle = computed(() => {
  if (isEdit.value) return '编辑菜单'
  if (form.value.parent_id) return '添加子菜单'
  return '新增菜单'
})

const getMenuTypeName = (type) => {
  const map = { directory: '目录', menu: '菜单', button: '按钮' }
  return map[type] || type
}

const getMenuTypeTag = (type) => {
  const map = { directory: 'warning', menu: 'success', button: 'info' }
  return map[type] || 'info'
}

// 扁平化菜单树
const flattenMenus = (menus, parentId = null) => {
  const result = []
  menus.forEach(menu => {
    result.push({ ...menu, parent_id: parentId })
    if (menu.children && menu.children.length > 0) {
      result.push(...flattenMenus(menu.children, menu.id))
    }
  })
  return result
}

// 获取同级菜单列表
const getSiblings = (menu) => {
  const parentId = menu.parent_id
  return flatMenuList.value.filter(m => m.parent_id === parentId).sort((a, b) => a.sort - b.sort)
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getMenuTree()
    tableData.value = res.data || []
    flatMenuList.value = flattenMenus(res.data || [])
  } catch (e) {
    // 错误已处理
  } finally {
    loading.value = false
  }
}

const fetchMenuOptions = async () => {
  try {
    const res = await getMenuTree()
    menuTreeOptions.value = [{ id: 0, name: '顶级菜单', children: res.data || [] }]
  } catch (e) {
    menuTreeOptions.value = [{ id: 0, name: '顶级菜单', children: [] }]
  }
}

const toggleExpandAll = () => {
  isExpandAll.value = !isExpandAll.value
  const data = tableData.value
  tableData.value = []
  setTimeout(() => {
    tableData.value = data
  }, 0)
}

// 上移菜单
const handleMoveUp = async (row) => {
  const siblings = getSiblings(row)
  const currentIndex = siblings.findIndex(m => m.id === row.id)

  if (currentIndex <= 0) {
    ElMessage.warning('已经是第一个了')
    return
  }

  const prevMenu = siblings[currentIndex - 1]
  const currentSort = row.sort
  const prevSort = prevMenu.sort

  try {
    // 交换排序值
    await updateMenu(row.id, { sort: prevSort })
    await updateMenu(prevMenu.id, { sort: currentSort })
    ElMessage.success('排序已更新')
    fetchData()
  } catch (e) {
    // 错误已处理
  }
}

// 下移菜单
const handleMoveDown = async (row) => {
  const siblings = getSiblings(row)
  const currentIndex = siblings.findIndex(m => m.id === row.id)

  if (currentIndex >= siblings.length - 1) {
    ElMessage.warning('已经是最后一个了')
    return
  }

  const nextMenu = siblings[currentIndex + 1]
  const currentSort = row.sort
  const nextSort = nextMenu.sort

  try {
    // 交换排序值
    await updateMenu(row.id, { sort: nextSort })
    await updateMenu(nextMenu.id, { sort: currentSort })
    ElMessage.success('排序已更新')
    fetchData()
  } catch (e) {
    // 错误已处理
  }
}

const handleAdd = () => {
  isEdit.value = false
  form.value = {
    parent_id: null,
    menu_type: 'menu',
    name: '',
    icon: '',
    path: '',
    component: '',
    permission: '',
    sort: 0,
    is_visible: true,
    is_cached: true
  }
  fetchMenuOptions()
  dialogVisible.value = true
}

const handleAddChild = (row) => {
  isEdit.value = false
  // 获取子菜单的最大排序值
  const children = row.children || []
  const maxSort = children.length > 0 ? Math.max(...children.map(c => c.sort || 0)) : 0

  form.value = {
    parent_id: row.id,
    menu_type: row.menu_type === 'directory' ? 'menu' : 'button',
    name: '',
    icon: '',
    path: '',
    component: '',
    permission: '',
    sort: maxSort + 1,
    is_visible: true,
    is_cached: true
  }
  fetchMenuOptions()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  form.value = {
    id: row.id,
    parent_id: row.parent_id || null,
    menu_type: row.menu_type,
    name: row.name,
    icon: row.icon || '',
    path: row.path || '',
    component: row.component || '',
    permission: row.permission || '',
    sort: row.sort || 0,
    is_visible: row.is_visible !== false,
    is_cached: row.is_cached !== false
  }
  fetchMenuOptions()
  dialogVisible.value = true
}

const handleSubmit = async () => {
  await formRef.value.validate()

  submitLoading.value = true
  try {
    const data = { ...form.value }
    if (data.parent_id === 0) data.parent_id = null

    if (isEdit.value) {
      await updateMenu(data.id, data)
      ElMessage.success('更新成功')
    } else {
      await createMenu(data)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    // 错误已处理
  } finally {
    submitLoading.value = false
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除菜单 "${row.name}" 吗？`, '提示', {
      type: 'warning'
    })
    await deleteMenu(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    // 取消或错误
  }
}

const resetForm = () => {
  formRef.value?.resetFields()
}

onMounted(() => {
  fetchData()
})
</script>

<style lang="scss" scoped>
.menu-management {
  .action-card {
    margin-bottom: 16px;

    .action-bar {
      display: flex;
      gap: 12px;
    }
  }

  .table-card {
    :deep(.el-table) {
      .el-table__row {
        .cell {
          display: flex;
          align-items: center;
        }
      }
    }

    .sort-actions {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 4px;

      .sort-value {
        min-width: 24px;
        text-align: center;
        font-weight: 500;
      }
    }
  }
}
</style>


