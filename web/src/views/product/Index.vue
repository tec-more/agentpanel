<template>
  <div class="product-management">
    <!-- 搜索栏 -->
    <el-card shadow="never" class="search-card">
      <el-form :inline="true" :model="searchForm" class="search-form">
        <el-form-item label="产品名称">
          <el-input v-model="searchForm.name" placeholder="请输入产品名称" clearable />
        </el-form-item>
        <el-form-item label="产品分类">
          <el-select v-model="searchForm.category" placeholder="请选择" clearable filterable style="width: 140px">
            <el-option v-for="cat in categoryOptions" :key="cat.value" :label="cat.label" :value="cat.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="产品类型">
          <el-select v-model="searchForm.is_stock_item" placeholder="请选择" clearable style="width: 130px">
            <el-option label="库存商品" :value="true" />
            <el-option label="虚拟商品" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="searchForm.is_active" placeholder="请选择" clearable style="width: 120px">
            <el-option label="上架" :value="true" />
            <el-option label="下架" :value="false" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 表格 -->
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>产品列表</span>
          <el-button type="primary" :icon="Plus" @click="handleAdd">新增产品</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="id" label="ID" width="80" align="center" />
        <el-table-column prop="product_code" label="产品编码" width="140" />
        <el-table-column prop="sort" label="排序" width="80" align="center" />
        <el-table-column prop="name" label="产品名称" min-width="120" />
        <el-table-column prop="description" label="产品描述" min-width="150" show-overflow-tooltip />
        <el-table-column label="价格" width="120" align="center">
          <template #default="{ row }">
            <div class="price-info">
              <div class="current-price">¥{{ row.price?.toFixed(2) || '0.00' }}</div>
              <div v-if="row.original_price && row.original_price > row.price" class="original-price">
                原价: ¥{{ row.original_price?.toFixed(2) }}
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="折扣" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.discount_percentage > 0" type="danger">
              {{ row.discount_percentage }}% off
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="时长信息" width="150" align="center">
          <template #default="{ row }">
            <div class="hours-info">
              <div>充值: {{ row.recharge_hours || 0 }}小时</div>
              <div v-if="row.bonus_hours > 0" class="bonus-hours">
                +赠送: {{ row.bonus_hours }}小时
              </div>
              <div class="total-hours">
                总计: {{ row.total_hours || 0 }}小时
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="stock" label="库存" width="100" align="center" />
        <el-table-column label="产品类型" width="110" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_stock_item" type="primary" size="small">库存商品</el-tag>
            <el-tag v-else type="info" size="small">虚拟商品</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="sales_count" label="销量" width="100" align="center" />
        <el-table-column prop="view_count" label="浏览" width="80" align="center" />
        <el-table-column label="标签" width="200" align="center">
          <template #default="{ row }">
            <div class="tags-wrapper">
              <el-tag v-if="row.is_hot" type="danger" size="small">热门</el-tag>
              <el-tag v-if="row.is_new" type="success" size="small">新品</el-tag>
              <el-tag
                v-for="(tag, index) in row.tags"
                :key="index"
                size="small"
                style="margin-left: 4px"
              >
                {{ tag }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" @change="handleToggleStatus(row)" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="250" fixed="right" align="center">
          <template #default="{ row }">
            <el-button type="primary" link :icon="View" @click="handleDetail(row)">详情</el-button>
            <el-button type="primary" link :icon="Edit" @click="handleEdit(row)">编辑</el-button>
            <el-button type="success" link :icon="Box" @click="handleUpdateStock(row)">库存</el-button>
            <el-button type="danger" link :icon="Delete" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchData"
          @current-change="fetchData"
        />
      </div>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑产品' : '新增产品'"
      width="700px"
      @close="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <!-- 产品类型切换 -->
        <el-form-item label="产品类型" prop="is_stock_item" v-if="!isEdit">
          <el-radio-group v-model="form.is_stock_item" @change="handleProductTypeChange">
            <el-radio-button :value="true">库存商品（实物）</el-radio-button>
            <el-radio-button :value="false">虚拟商品（会员/充值）</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <!-- 库存商品：从物料表选取 -->
        <el-form-item
          label="关联物料"
          prop="material_id"
          v-if="form.is_stock_item && !isEdit"
        >
          <el-select
            v-model="form.material_id"
            placeholder="请选择成品物料"
            filterable
            remote
            :remote-method="searchMaterials"
            :loading="materialLoading"
            style="width: 100%"
            @change="handleMaterialSelect"
            :disabled="materialOptions.length === 0"
          >
            <el-option
              v-for="item in materialOptions"
              :key="item.id"
              :label="`${item.material_code} - ${item.material_name}`"
              :value="item.id"
            >
              <span style="float: left">{{ item.material_code }} - {{ item.material_name }}</span>
              <span style="float: right; color: #999; font-size: 12px">{{ item.specification }}</span>
            </el-option>
          </el-select>
          <div v-if="materialOptions.length === 0" style="font-size: 12px; color: #f56c6c; margin-top: 4px">
            ⚠ 没有可关联的成品物料，请先在【MES-基础数据-物料管理】中创建成品物料（类型选择finished）
          </div>
          <div v-else style="font-size: 12px; color: #999; margin-top: 4px">
            选择成品物料后，产品编码/名称/描述将自动从物料信息填充
          </div>
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="产品编码" prop="product_code">
              <el-input
                v-model="form.product_code"
                placeholder="请选择物料后自动填充"
                :disabled="form.is_stock_item && form.material_id"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="产品名称" prop="name">
              <el-input
                v-model="form.name"
                placeholder="请输入产品名称"
                :disabled="form.is_stock_item && form.material_id"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="排序" prop="sort">
              <el-input-number v-model="form.sort" :min="0" :step="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="产品描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            placeholder="请输入产品描述"
            rows="2"
            :disabled="form.is_stock_item && form.material_id"
          />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="产品分类" prop="category">
              <el-select v-model="form.category" placeholder="请选择分类" style="width: 100%" allow-create filterable>
                <el-option v-for="cat in categoryOptions" :key="cat.value" :label="cat.label" :value="cat.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="库存" prop="stock" v-if="form.is_stock_item">
              <el-input-number v-model="form.stock" :min="0" :step="10" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="销售价格" prop="price">
              <el-input-number v-model="form.price" :min="0.01" :step="0.01" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="原价" prop="original_price">
              <el-input-number v-model="form.original_price" :min="0" :step="0.01" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="优惠描述" prop="discount_description">
              <el-input v-model="form.discount_description" placeholder="如:限时8折" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 虚拟商品专属字段 -->
        <template v-if="!form.is_stock_item">
          <el-row :gutter="20">
            <el-col :span="8">
              <el-form-item label="充值时长" prop="recharge_hours">
                <el-input-number v-model="form.recharge_hours" :min="0" :step="1" style="width: 100%" />
                <span style="margin-left: 8px; color: #999; font-size: 12px">小时</span>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="赠送时长" prop="bonus_hours">
                <el-input-number v-model="form.bonus_hours" :min="0" :step="1" style="width: 100%" />
                <span style="margin-left: 8px; color: #999; font-size: 12px">小时</span>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item label="产品标签" prop="tags">
                <el-select v-model="form.tags" multiple placeholder="选择标签" style="width: 100%">
                  <el-option label="升级 LV.1" value="升级 LV.1" />
                  <el-option label="升级 LV.4" value="升级 LV.4" />
                  <el-option label="升级 LV.7" value="升级 LV.7" />
                  <el-option label="升级 LV.9" value="升级 LV.9" />
                  <el-option label="升级 LV.11" value="升级 LV.11" />
                  <el-option label="限时9折" value="限时9折" />
                  <el-option label="限时8折" value="限时8折" />
                  <el-option label="限时75折" value="限时75折" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>
        </template>

        <!-- 库存商品标签 -->
        <template v-if="form.is_stock_item">
          <el-form-item label="产品标签" prop="tags">
            <el-select v-model="form.tags" multiple placeholder="选择标签" style="width: 100%" allow-create filterable>
              <el-option label="热门" value="热门" />
              <el-option label="新品" value="新品" />
              <el-option label="限量" value="限量" />
              <el-option label="促销" value="促销" />
            </el-select>
          </el-form-item>
        </template>

        <el-form-item label="产品特性">
          <el-checkbox v-model="form.is_active">上架</el-checkbox>
          <el-checkbox v-model="form.is_hot">热门</el-checkbox>
          <el-checkbox v-model="form.is_new">新品</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 库存管理弹窗 -->
    <el-dialog v-model="stockDialogVisible" title="库存管理" width="400px">
      <div class="stock-dialog-content">
        <p class="stock-tip">当前产品: <strong>{{ currentProduct?.name }}</strong></p>
        <p class="stock-tip">当前库存: <strong>{{ currentProduct?.stock }}</strong></p>
        <el-form ref="stockFormRef" :model="stockForm" :rules="stockRules" label-width="80px">
          <el-form-item label="调整数量" prop="stock">
            <el-input-number v-model="stockForm.stock" :step="10" style="width: 100%" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="stockDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="stockLoading" @click="handleStockSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, Edit, Delete, Box, View } from '@element-plus/icons-vue'
import {
  getProductList,
  createProduct,
  updateProduct,
  deleteProduct,
  toggleProductStatus,
  updateProductStock,
  getAvailableMaterials,
  getCategoryOptions
} from '@/api/product'

const loading = ref(false)
const submitLoading = ref(false)
const stockLoading = ref(false)
const materialLoading = ref(false)
const dialogVisible = ref(false)
const stockDialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const stockFormRef = ref(null)
const router = useRouter()

const tableData = ref([])
const currentProduct = ref(null)
const materialOptions = ref([])
const categoryOptions = ref([])

const searchForm = reactive({
  name: '',
  category: null,
  is_stock_item: null,
  is_active: null
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0
})

const form = ref({
  product_code: '',
  name: '',
  description: '',
  price: 0,
  original_price: null,
  stock: 0,
  sort: 0,
  category: '',
  is_stock_item: true,
  material_id: null,
  recharge_hours: 0,
  bonus_hours: 0,
  tags: [],
  is_active: true,
  is_hot: false,
  is_new: false,
  discount_description: null
})

const stockForm = reactive({
  stock: 0
})

const rules = {
  name: [
    { required: true, message: '请输入产品名称', trigger: 'blur' },
    { min: 2, max: 50, message: '产品名称长度在2-50个字符', trigger: 'blur' }
  ],
  price: [
    { required: true, message: '请输入价格', trigger: 'blur' },
    { type: 'number', min: 0.01, message: '价格不能少于0.01', trigger: 'blur' }
  ],
  category: [
    { required: true, message: '请选择产品分类', trigger: 'change' }
  ]
}

const stockRules = {
  stock: [
    { required: true, message: '请输入调整数量', trigger: 'blur' },
    { type: 'number', message: '请输入有效数字', trigger: 'blur' }
  ]
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getProductList({
      page: pagination.page,
      page_size: pagination.pageSize,
      ...searchForm
    })
    tableData.value = res.data.items
    pagination.total = res.data.total
  } catch (e) {
    // 错误已处理
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  pagination.page = 1
  fetchData()
}

const handleReset = () => {
  searchForm.name = ''
  searchForm.category = null
  searchForm.is_stock_item = null
  searchForm.is_active = null
  handleSearch()
}

const handleDetail = (row) => {
  router.push(`/panel/product/${row.id}`)
}

const handleAdd = () => {
  isEdit.value = false
  form.value = {
    product_code: '',
    name: '',
    description: '',
    price: 0,
    original_price: null,
    stock: 0,
    sort: 0,
    category: '',
    is_stock_item: true,
    material_id: null,
    recharge_hours: 0,
    bonus_hours: 0,
    tags: [],
    is_active: true,
    is_hot: false,
    is_new: false,
    discount_description: null
  }
  materialOptions.value = []
  loadMaterials()
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  form.value = {
    id: row.id,
    product_code: row.product_code || '',
    name: row.name,
    description: row.description || '',
    price: row.price,
    original_price: row.original_price,
    stock: row.stock,
    sort: row.sort || 0,
    category: row.category,
    is_stock_item: row.is_stock_item !== undefined ? row.is_stock_item : true,
    material_id: null,
    recharge_hours: row.recharge_hours,
    bonus_hours: row.bonus_hours,
    tags: row.tags || [],
    is_active: row.is_active,
    is_hot: row.is_hot,
    is_new: row.is_new,
    discount_description: row.discount_description
  }
  dialogVisible.value = true
}

const loadMaterials = async (keyword) => {
  materialLoading.value = true
  try {
    const res = await getAvailableMaterials({ keyword, include_linked: false })
    materialOptions.value = res.data.items
  } catch (e) {
    // 错误已处理
  } finally {
    materialLoading.value = false
  }
}

const loadCategories = async () => {
  try {
    const res = await getCategoryOptions()
    categoryOptions.value = res.data
  } catch (e) {
    // 错误已处理
  }
}

const searchMaterials = (query) => {
  if (query) {
    loadMaterials(query)
  } else {
    loadMaterials()
  }
}

const handleMaterialSelect = (materialId) => {
  const material = materialOptions.value.find(m => m.id === materialId)
  if (material) {
    form.value.product_code = material.material_code
    form.value.name = material.material_name
    form.value.description = `物料编码: ${material.material_code}，规格: ${material.specification || '-'}，单位: ${material.unit || '-'}`
    form.value.stock = material.initial_stock || 0
    nextTick(() => {
      formRef.value && formRef.value.clearValidate(['name', 'product_code'])
    })
  }
}

const handleProductTypeChange = (val) => {
  form.value.material_id = null
  if (!val) {
    form.value.recharge_hours = 0
    form.value.bonus_hours = 0
    form.value.stock = 0
  }
}

const handleSubmit = async () => {
  await formRef.value.validate()

  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateProduct(form.value.id, {
        name: form.value.name,
        description: form.value.description,
        price: form.value.price,
        original_price: form.value.original_price,
        stock: form.value.stock,
        sort: form.value.sort,
        category: form.value.category,
        is_stock_item: form.value.is_stock_item,
        recharge_hours: form.value.recharge_hours,
        bonus_hours: form.value.bonus_hours,
        tags: form.value.tags,
        is_active: form.value.is_active,
        is_hot: form.value.is_hot,
        is_new: form.value.is_new,
        discount_description: form.value.discount_description
      })
      ElMessage.success('更新成功')
    } else {
      await createProduct({
        name: form.value.name,
        description: form.value.description,
        price: form.value.price,
        original_price: form.value.original_price,
        stock: form.value.stock,
        sort: form.value.sort,
        category: form.value.category,
        is_stock_item: form.value.is_stock_item,
        material_id: form.value.material_id,
        recharge_hours: form.value.recharge_hours,
        bonus_hours: form.value.bonus_hours,
        tags: form.value.tags,
        is_active: form.value.is_active,
        is_hot: form.value.is_hot,
        is_new: form.value.is_new,
        discount_description: form.value.discount_description
      })
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
    await ElMessageBox.confirm(`确定要删除产品 "${row.name}" 吗？`, '提示', {
      type: 'warning'
    })
    await deleteProduct(row.id)
    ElMessage.success('删除成功')
    fetchData()
  } catch (e) {
    // 取消或错误
  }
}

const handleToggleStatus = async (row) => {
  try {
    await toggleProductStatus(row.id)
    ElMessage.success(row.is_active ? '已上架' : '已下架')
  } catch (e) {
    row.is_active = !row.is_active
  }
}

const handleUpdateStock = (row) => {
  currentProduct.value = row
  stockForm.stock = 0
  stockDialogVisible.value = true
}

const handleStockSubmit = async () => {
  await stockFormRef.value.validate()

  stockLoading.value = true
  try {
    await updateProductStock(currentProduct.value.id, {
      stock: stockForm.stock
    })
    ElMessage.success('库存调整成功')
    stockDialogVisible.value = false
    fetchData()
  } catch (e) {
    // 错误已处理
  } finally {
    stockLoading.value = false
  }
}

const resetForm = () => {
  formRef.value?.resetFields()
  stockFormRef.value?.resetFields()
}

onMounted(() => {
  fetchData()
  loadCategories()
})
</script>

<style lang="scss" scoped>
.product-management {
  .search-card {
    margin-bottom: 16px;

    .search-form {
      display: flex;
      flex-wrap: wrap;

      .el-form-item {
        margin-bottom: 0;
        margin-right: 16px;
      }
    }
  }

  .table-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
  }

  .pagination-wrapper {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }

  .price-info {
    .current-price {
      font-weight: bold;
      color: #f56c6c;
    }
    .original-price {
      font-size: 12px;
      color: #999;
      text-decoration: line-through;
    }
  }

  .hours-info {
    font-size: 12px;
    .bonus-hours {
      color: #67c23a;
      font-weight: bold;
    }
    .total-hours {
      font-weight: bold;
      color: #409eff;
      margin-top: 4px;
    }
  }

  .tags-wrapper {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    justify-content: center;
  }

  .stock-dialog-content {
    .stock-tip {
      margin-bottom: 16px;
      color: #666;
    }
  }
}
</style>


