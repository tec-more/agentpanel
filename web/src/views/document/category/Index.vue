<template>
  <div class="document-category">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>分类目录管理</span>
          <el-button type="primary" :icon="Plus" @click="handleCreate">
            新建分类
          </el-button>
        </div>
      </template>

      <el-table :data="treeData" v-loading="loading" row-key="id" default-expand-all>
        <el-table-column prop="name" label="分类名称" />
        <el-table-column prop="sort" label="排序" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="handleEdit(row)">
              编辑
            </el-button>
            <el-button
              link
              type="primary"
              size="small"
              @click="handleAddChild(row)"
            >
              添加子分类
            </el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog
      v-model="showDialog"
      :title="editingCategory ? '编辑分类' : '新建分类'"
      width="450px"
    >
      <el-form :model="form" label-width="80px">
        <el-form-item label="分类名称" required>
          <el-input v-model="form.name" placeholder="请输入分类名称" />
        </el-form-item>
        <el-form-item label="上级分类">
          <el-tree-select
            v-model="form.parent_id"
            :data="flatCategories"
            :props="{ label: 'name', value: 'id' }"
            placeholder="不选择则为根分类"
            check-strictly
            clearable
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort" :min="0" :max="9999" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { getCategoryTree, createCategory, updateCategory, deleteCategory } from '@/api/document'

const loading = ref(false)
const treeData = ref([])
const flatCategories = ref([])
const showDialog = ref(false)
const editingCategory = ref(null)

const form = reactive({
  name: '',
  parent_id: null,
  sort: 0,
  is_active: true
})

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getCategoryTree()
    if (res.code === 0) {
      treeData.value = res.data
      const flat = []
      const flatten = (items, level = 0) => {
        items.forEach(item => {
          flat.push({
            id: item.id,
            name: '　'.repeat(level) + item.name,
            rawName: item.name,
            parent_id: item.parent_id
          })
          if (item.children && item.children.length) {
            flatten(item.children, level + 1)
          }
        })
      }
      flatten(res.data)
      flatCategories.value = flat
    }
  } catch (e) {
    ElMessage.error('获取分类失败')
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  form.name = ''
  form.parent_id = null
  form.sort = 0
  form.is_active = true
  editingCategory.value = null
}

const handleCreate = () => {
  resetForm()
  showDialog.value = true
}

const handleAddChild = (row) => {
  resetForm()
  form.parent_id = row.id
  showDialog.value = true
}

const handleEdit = (row) => {
  resetForm()
  editingCategory.value = row
  form.name = row.name
  form.parent_id = row.parent_id
  form.sort = row.sort || 0
  form.is_active = row.is_active
  showDialog.value = true
}

const handleSave = async () => {
  if (!form.name) {
    ElMessage.warning('请输入分类名称')
    return
  }
  
  try {
    const data = {
      name: form.name,
      parent_id: form.parent_id,
      sort: form.sort,
      is_active: form.is_active
    }
    
    let res
    if (editingCategory.value) {
      res = await updateCategory(editingCategory.value.id, data)
    } else {
      res = await createCategory(data)
    }
    
    if (res.code === 0) {
      ElMessage.success('保存成功')
      showDialog.value = false
      fetchData()
    } else {
      ElMessage.error(res.msg || '保存失败')
    }
  } catch (e) {
    ElMessage.error('保存失败: ' + e.message)
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(`确定要删除分类「${row.name}」吗？`, '确认删除', {
      type: 'warning',
      message: '删除前请确保该分类下没有子分类和文档'
    })
    const res = await deleteCategory(row.id)
    if (res.code === 0) {
      ElMessage.success('删除成功')
      fetchData()
    }
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style lang="scss" scoped>
.document-category {
  padding: 20px;
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>
