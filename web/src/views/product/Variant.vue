<template>
  <div class="page-container">
    <el-card class="filter-card">
      <el-row :gutter="20">
        <el-col :span="8">
          <el-select v-model="searchForm.product_id" placeholder="请选择产品" clearable filterable style="width: 100%">
            <el-option v-for="p in productOptions" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-col>
        <el-col :span="8">
          <el-input v-model="searchForm.sku" placeholder="SKU" clearable @keyup.enter="fetchData">
            <template #prefix><Search /></template>
          </el-input>
        </el-col>
        <el-col :span="8" class="flex justify-end">
          <el-button type="primary" :icon="Plus" @click="openAddDialog">新增变体</el-button>
        </el-col>
      </el-row>
    </el-card>

    <el-card class="table-card">
      <el-table :data="tableData" v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="sku" label="SKU" />
        <el-table-column prop="attributes" label="属性组合" width="200">
          <template #default="scope">
            <span v-if="scope.row.attributes">{{ formatAttributes(scope.row.attributes) }}</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="价格" width="100">
          <template #default="scope">¥{{ scope.row.price?.toFixed(2) || '-' }}</template>
        </el-table-column>
        <el-table-column prop="original_price" label="原价" width="100">
          <template #default="scope">¥{{ scope.row.original_price?.toFixed(2) || '-' }}</template>
        </el-table-column>
        <el-table-column prop="stock" label="库存" width="80" />
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="scope">
            <el-tag :type="scope.row.is_active ? 'success' : 'danger'">
              {{ scope.row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="scope">
            <el-button size="small" @click="openEditDialog(scope.row)">编辑</el-button>
            <el-button size="small" type="danger" @click="handleDelete(scope.row)">删除</el-button>
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

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑产品变体' : '新增产品变体'" width="600px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="所属产品" prop="product_id">
          <el-select v-model="form.product_id" placeholder="请选择产品" style="width: 100%" filterable @change="handleProductChange">
            <el-option v-for="p in productOptions" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="SKU编码" prop="sku">
          <el-input v-model="form.sku" placeholder="请输入SKU编码" />
        </el-form-item>
        <el-form-item label="属性组合">
          <div v-for="attr in availableAttributes" :key="attr.code" class="mb-2">
            <span>{{ attr.name }}:</span>
            <el-select v-model="form.attributes[attr.code]" placeholder="请选择" style="width: 200px; margin-left: 10px">
              <el-option v-for="val in attr.values" :key="val" :label="val" :value="val" />
            </el-select>
          </div>
          <div v-if="availableAttributes.length === 0" class="text-gray-400">请先选择产品或添加属性</div>
        </el-form-item>
        <el-form-item label="价格" prop="price">
          <el-input-number v-model="form.price" :min="0.01" :step="0.01" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="原价">
          <el-input-number v-model="form.original_price" :min="0.01" :step="0.01" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="库存" prop="stock">
          <el-input-number v-model="form.stock" :min="0" :step="10" style="width: 100%" />
        </el-form-item>
        <el-form-item label="关联物料变体">
          <el-select v-model="form.material_variant_id" placeholder="请选择物料变体" style="width: 100%" filterable>
            <el-option v-for="mv in materialVariants" :key="mv.id" :label="mv.variant_code" :value="mv.id" />
          </el-select>
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
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { Search, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getProductVariantList,
  createProductVariant,
  updateProductVariant,
  deleteProductVariant,
  getProductList,
  getMaterialVariantList,
  getAttributeList,
  getAttributeValues
} from '@/api/product'

const loading = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const searchForm = reactive({ product_id: null, sku: '' })
const pagination = reactive({ page: 1, pageSize: 10, total: 0 })

const form = reactive({
  id: null,
  product_id: null,
  sku: '',
  attributes: {},
  price: 0,
  original_price: null,
  stock: 0,
  material_variant_id: null,
  is_active: true
})

const productOptions = ref([])
const materialVariants = ref([])
const allAttributes = ref([])

const rules = {
  product_id: [{ required: true, message: '请选择产品', trigger: 'blur' }],
  sku: [{ required: true, message: '请输入SKU编码', trigger: 'blur' }],
  price: [{ required: true, message: '请输入价格', trigger: 'blur' }]
}

const availableAttributes = computed(() => {
  return allAttributes.value.map(attr => ({
    ...attr,
    values: []
  }))
})

const formatAttributes = (attrs) => {
  return Object.entries(attrs).map(([k, v]) => `${k}: ${v}`).join(', ')
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getProductVariantList({ ...searchForm, page: pagination.page, page_size: pagination.pageSize })
    tableData.value = res.data.items
    pagination.total = res.data.total
  } catch (e) { ElMessage.error('获取变体列表失败') }
  finally { loading.value = false }
}

const loadProducts = async () => {
  try {
    const res = await getProductList({ page: 1, page_size: 100 })
    productOptions.value = res.data.items.map(p => ({ id: p.id, name: p.name }))
  } catch (e) { }
}

const loadMaterialVariants = async () => {
  try {
    const res = await getMaterialVariantList({ page: 1, page_size: 100 })
    materialVariants.value = res.data.items
  } catch (e) { }
}

const loadAttributes = async () => {
  try {
    const res = await getAttributeList({ page: 1, page_size: 100 })
    allAttributes.value = await Promise.all(res.data.items.map(async attr => {
      const valuesRes = await getAttributeValues(attr.id)
      return { ...attr, values: valuesRes.data.map(v => v.value) }
    }))
  } catch (e) { }
}

const handleProductChange = () => {
  form.attributes = {}
}

const openAddDialog = () => {
  isEdit.value = false
  Object.assign(form, { id: null, product_id: null, sku: '', attributes: {}, price: 0, original_price: null, stock: 0, material_variant_id: null, is_active: true })
  dialogVisible.value = true
}

const openEditDialog = (row) => {
  isEdit.value = true
  Object.assign(form, { ...row, attributes: row.attributes || {} })
  dialogVisible.value = true
}

const handleSubmit = async () => {
  await formRef.value.validate()
  try {
    const data = { ...form }
    if (Object.keys(data.attributes).length === 0) data.attributes = null
    if (isEdit.value) {
      await updateProductVariant(form.id, data)
      ElMessage.success('变体更新成功')
    } else {
      await createProductVariant(data)
      ElMessage.success('变体创建成功')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) { ElMessage.error(e.message || '操作失败') }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除该变体？', '提示', { type: 'warning' })
    await deleteProductVariant(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) { if (e !== 'cancel') ElMessage.error(e.message || '删除失败') }
}

onMounted(() => {
  fetchData()
  loadProducts()
  loadMaterialVariants()
  loadAttributes()
})
</script>