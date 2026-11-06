<template>
  <div class="page-container">
    <el-card class="filter-card">
      <el-row :gutter="20">
        <el-col :span="8">
          <el-input v-model="searchForm.name" placeholder="属性名称" clearable @keyup.enter="fetchData">
            <template #prefix><Search /></template>
          </el-input>
        </el-col>
        <el-col :span="8">
          <el-select v-model="searchForm.category" placeholder="属性类别" clearable>
            <el-option label="产品属性" value="product" />
            <el-option label="物料属性" value="material" />
            <el-option label="通用属性" value="both" />
          </el-select>
        </el-col>
        <el-col :span="8" class="flex justify-end">
          <el-button type="primary" :icon="Plus" @click="openAddDialog">新增属性</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card class="table-card">
      <el-table :data="tableData" v-loading="loading" @row-click="handleRowClick">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="属性名称" />
        <el-table-column prop="code" label="属性编码" />
        <el-table-column prop="category" label="类别" width="100">
          <template #default="scope">
            <el-tag :type="scope.row.category === 'both' ? 'success' : 'info'">
              {{ scope.row.category === 'both' ? '通用' : (scope.row.category === 'product' ? '产品' : '物料') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sort" label="排序" width="80" />
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="scope">
            <el-tag :type="scope.row.is_active ? 'success' : 'danger'">
              {{ scope.row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="openEditDialog(scope.row)">编辑</el-button>
            <el-button size="small" @click="openValuesDialog(scope.row)">管理值</el-button>
            <el-button size="small" type="danger" @click="handleDelete(scope.row)" :disabled="scope.row.is_active">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑属性' : '新增属性'" width="500px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="属性名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入属性名称" />
        </el-form-item>
        <el-form-item label="属性编码" prop="code">
          <el-input v-model="form.code" placeholder="请输入属性编码（英文）" />
        </el-form-item>
        <el-form-item label="属性类别" prop="category">
          <el-select v-model="form.category" placeholder="请选择">
            <el-option label="产品属性" value="product" />
            <el-option label="物料属性" value="material" />
            <el-option label="通用属性" value="both" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序" prop="sort">
          <el-input-number v-model="form.sort" :min="0" :step="1" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="valuesDialogVisible" :title="`管理属性值 - ${currentAttr?.name}`" width="600px">
      <el-form :model="valueForm" label-width="80px" class="mb-4">
        <el-form-item label="属性值">
          <el-row :gutter="10">
            <el-col :span="18">
              <el-input v-model="valueForm.value" placeholder="请输入属性值" @keyup.enter="addValue" />
            </el-col>
            <el-col :span="6">
              <el-button type="primary" @click="addValue" style="width: 100%">添加</el-button>
            </el-col>
          </el-row>
        </el-form-item>
      </el-form>
      <el-table :data="attrValues" v-loading="valuesLoading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="value" label="属性值" />
        <el-table-column prop="sort" label="排序" width="80">
          <template #default="scope">
            <el-input-number v-model="scope.row.sort" :min="0" :step="1" @change="updateValueSort(scope.row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="scope">
            <el-button size="small" @click="editValue(scope.row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deleteValue(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="valuesDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { Search, Plus, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getAttributeList,
  createAttribute,
  updateAttribute,
  deleteAttribute,
  getAttributeValues,
  createAttributeValue,
  updateAttributeValue,
  deleteAttributeValue
} from '@/api/product'

const loading = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const valuesDialogVisible = ref(false)
const valuesLoading = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const currentAttr = ref(null)
const attrValues = ref([])

const searchForm = reactive({ name: '', category: '' })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const form = reactive({ id: null, name: '', code: '', category: 'both', sort: 0, is_active: true })
const valueForm = reactive({ value: '' })

const rules = {
  name: [{ required: true, message: '请输入属性名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入属性编码', trigger: 'blur' }],
  category: [{ required: true, message: '请选择属性类别', trigger: 'blur' }]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getAttributeList({ ...searchForm, page: pagination.page, page_size: pagination.pageSize })
    tableData.value = res.data.items
    pagination.total = res.data.total
  } catch (e) { ElMessage.error('获取属性列表失败') }
  finally { loading.value = false }
}

const openAddDialog = () => {
  isEdit.value = false
  Object.assign(form, { id: null, name: '', code: '', category: 'both', sort: 0, is_active: true })
  dialogVisible.value = true
}

const openEditDialog = (row) => {
  isEdit.value = true
  Object.assign(form, row)
  dialogVisible.value = true
}

const handleSubmit = async () => {
  await formRef.value.validate()
  try {
    if (isEdit.value) {
      await updateAttribute(form.id, form)
      ElMessage.success('属性更新成功')
    } else {
      await createAttribute(form)
      ElMessage.success('属性创建成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.message || '操作失败') }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除该属性？', '提示', { type: 'warning' })
    await deleteAttribute(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

const openValuesDialog = async (row) => {
  currentAttr.value = row
  valuesDialogVisible.value = true
  await loadAttributeValues(row.id)
}

const loadAttributeValues = async (attrId) => {
  valuesLoading.value = true
  try {
    const res = await getAttributeValues(attrId)
    attrValues.value = res.data
  } catch (e) { ElMessage.error('获取属性值失败') }
  finally { valuesLoading.value = false }
}

const addValue = async () => {
  if (!valueForm.value.trim()) return
  try {
    await createAttributeValue({ attribute_id: currentAttr.value.id, value: valueForm.value.trim() })
    valueForm.value = ''
    await loadAttributeValues(currentAttr.value.id)
    ElMessage.success('添加成功')
  } catch (e) { ElMessage.error(e.message || '添加失败') }
}

const editValue = (row) => {
  const newValue = prompt('请输入新的属性值', row.value)
  if (newValue !== null && newValue.trim() !== row.value) {
    updateAttributeValue(row.id, { value: newValue.trim() })
      .then(() => { row.value = newValue.trim(); ElMessage.success('更新成功') })
      .catch(e => ElMessage.error(e.message))
  }
}

const updateValueSort = (row) => {
  updateAttributeValue(row.id, { sort: row.sort })
    .catch(e => ElMessage.error(e.message))
}

const deleteValue = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除该属性值？', '提示', { type: 'warning' })
    await deleteAttributeValue(row.id)
    attrValues.value = attrValues.value.filter(v => v.id !== row.id)
    ElMessage.success('删除成功')
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

fetchData()
</script>