<template>
  <div class="product-detail">
    <el-card shadow="never" class="detail-card">
      <template #header>
        <div class="card-header">
          <el-button type="primary" :icon="Back" @click="handleBack">返回列表</el-button>
          <span class="detail-title">产品详情</span>
        </div>
      </template>

      <div class="loading-container" v-if="loading">
        <el-skeleton :rows="10" animated />
      </div>

      <div v-else class="detail-content">
        <el-row :gutter="24">
          <el-col :span="24" class="detail-info">
            <h2 class="product-name">{{ product?.name }}</h2>
            <el-divider />
            <el-row :gutter="20">
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">产品ID:</span>
                  <span class="info-value">{{ product?.id }}</span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">产品类型:</span>
                  <el-tag v-if="product?.category === '充值套餐'" type="success">
                    充值套餐
                  </el-tag>
                  <el-tag v-else-if="product?.category === '会员套餐'" type="warning">
                    会员套餐
                  </el-tag>
                  <el-tag v-else type="info">
                    其他
                  </el-tag>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">价格:</span>
                  <span class="info-value price">¥{{ product?.price?.toFixed(2) || '0.00' }}</span>
                </div>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">原价:</span>
                  <span class="info-value">
                    <span v-if="product?.original_price" style="text-decoration: line-through; color: #999;">
                      ¥{{ product?.original_price?.toFixed(2) }}
                    </span>
                    <span v-else>-</span>
                  </span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">库存:</span>
                  <span class="info-value">{{ product?.stock }}</span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">销售数量:</span>
                  <span class="info-value">{{ product?.sales_count }}</span>
                </div>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">浏览次数:</span>
                  <span class="info-value">{{ product?.view_count }}</span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">状态:</span>
                  <el-tag v-if="product?.is_active" type="success">
                    启用
                  </el-tag>
                  <el-tag v-else type="danger">
                    禁用
                  </el-tag>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">热门产品:</span>
                  <el-tag v-if="product?.is_hot" type="warning">
                    是
                  </el-tag>
                  <el-tag v-else type="info">
                    否
                  </el-tag>
                </div>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">新品:</span>
                  <el-tag v-if="product?.is_new" type="primary">
                    是
                  </el-tag>
                  <el-tag v-else type="info">
                    否
                  </el-tag>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">创建时间:</span>
                  <span class="info-value">{{ product?.created_at }}</span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">更新时间:</span>
                  <span class="info-value">{{ product?.updated_at }}</span>
                </div>
              </el-col>
            </el-row>

            <el-divider />
            <div class="detail-section">
              <h3 class="section-title">产品描述</h3>
              <p class="description">{{ product?.description || '无描述' }}</p>
            </div>

            <div class="detail-section">
              <h3 class="section-title">分类与标签</h3>
              <div class="info-item">
                <span class="info-label">分类:</span>
                <span class="info-value">{{ product?.category || '无分类' }}</span>
              </div>
              <div class="info-item">
                <span class="info-label">标签:</span>
                <el-tag v-for="tag in product?.tags" :key="tag" type="info" size="small" class="tag-item">
                  {{ tag }}
                </el-tag>
                <span v-if="!product?.tags || product?.tags.length === 0" class="no-tags">无标签</span>
              </div>
            </div>

            <div class="detail-section" v-if="!product?.is_stock_item">
              <h3 class="section-title">时长信息</h3>
              <el-row :gutter="20">
                <el-col :span="8">
                  <div class="info-item">
                    <span class="info-label">充值时长:</span>
                    <span class="info-value">{{ product?.recharge_hours || 0 }} 小时</span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="info-item">
                    <span class="info-label">赠送时长:</span>
                    <span class="info-value">{{ product?.bonus_hours || 0 }} 小时</span>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="info-item">
                    <span class="info-label">总时长:</span>
                    <span class="info-value">{{ product?.total_hours || 0 }} 小时</span>
                  </div>
                </el-col>
              </el-row>
            </div>

            <div class="detail-section" v-if="product?.images && product.images.length > 0">
              <h3 class="section-title">产品图片</h3>
              <el-image
                v-for="(image, index) in product?.images"
                :key="index"
                :src="image"
                :preview-src-list="product?.images"
                class="product-image"
              />
            </div>

            <div class="detail-actions">
              <el-button type="primary" :icon="Edit" @click="openEditDialog">编辑</el-button>
              <el-button v-if="product?.is_active" type="warning" :icon="SwitchButton" @click="handleToggleStatus">禁用</el-button>
              <el-button v-else type="success" :icon="SwitchButton" @click="handleToggleStatus">启用</el-button>
              <el-button type="danger" :icon="Delete" @click="handleDelete">删除</el-button>
            </div>
          </el-col>
        </el-row>
      </div>
    </el-card>

    <!-- 编辑弹窗 -->
    <el-dialog
      v-model="editDialogVisible"
      title="编辑产品"
      width="700px"
      @close="resetEditForm"
    >
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="产品名称" prop="name">
              <el-input v-model="editForm.name" placeholder="请输入产品名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="排序" prop="sort">
              <el-input-number v-model="editForm.sort" :min="0" :step="1" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="产品描述" prop="description">
          <el-input v-model="editForm.description" type="textarea" placeholder="请输入产品描述" rows="2" />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="产品分类" prop="category">
              <el-select v-model="editForm.category" placeholder="请选择分类" style="width: 100%">
                <el-option v-for="cat in categoryOptions" :key="cat.value" :label="cat.label" :value="cat.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="库存" prop="stock">
              <el-input-number v-model="editForm.stock" :min="0" :step="10" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="销售价格" prop="price">
              <el-input-number v-model="editForm.price" :min="0.01" :step="0.01" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="原价" prop="original_price">
              <el-input-number v-model="editForm.original_price" :min="0" :step="0.01" :precision="2" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="优惠描述" prop="discount_description">
              <el-input v-model="editForm.discount_description" placeholder="如:限时8折" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20" v-if="!editForm.is_stock_item">
          <el-col :span="8">
            <el-form-item label="充值时长" prop="recharge_hours">
              <el-input-number v-model="editForm.recharge_hours" :min="0" :step="1" style="width: 100%" />
              <span style="margin-left: 8px; color: #999; font-size: 12px">小时</span>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="赠送时长" prop="bonus_hours">
              <el-input-number v-model="editForm.bonus_hours" :min="0" :step="1" style="width: 100%" />
              <span style="margin-left: 8px; color: #999; font-size: 12px">小时</span>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="产品标签" prop="tags">
              <el-select v-model="editForm.tags" multiple placeholder="选择标签" style="width: 100%">
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

        <el-row :gutter="20" v-if="editForm.is_stock_item">
          <el-col :span="24">
            <el-form-item label="产品标签" prop="tags">
              <el-select v-model="editForm.tags" multiple placeholder="选择标签" style="width: 100%">
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

        <el-form-item label="产品特性">
          <el-checkbox v-model="editForm.is_active">上架</el-checkbox>
          <el-checkbox v-model="editForm.is_hot">热门</el-checkbox>
          <el-checkbox v-model="editForm.is_new">新品</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitLoading" @click="handleEditSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, Edit, Delete, SwitchButton } from '@element-plus/icons-vue'
import { getProductDetail, toggleProductStatus, deleteProduct, updateProduct, getCategoryOptions } from '@/api/product'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const editSubmitLoading = ref(false)
const editDialogVisible = ref(false)
const product = ref(null)
const editFormRef = ref(null)
const categoryOptions = ref([])

const productId = computed(() => route.params.id)

const editForm = ref({
  name: '',
  description: '',
  price: 0,
  original_price: null,
  stock: 0,
  sort: 0,
  category: '充值套餐',
  recharge_hours: 0,
  bonus_hours: 0,
  tags: [],
  is_active: true,
  is_hot: false,
  is_new: false,
  discount_description: null
})

const editRules = {
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

const fetchProductDetail = async () => {
  if (!productId.value) return

  loading.value = true
  try {
    const res = await getProductDetail(productId.value)
    product.value = res.data
  } catch (e) {
    // 错误已处理
  } finally {
    loading.value = false
  }
}

const handleBack = () => {
  router.push('/panel/product')
}

const openEditDialog = () => {
  editForm.value = {
    name: product.value.name,
    description: product.value.description || '',
    price: product.value.price,
    original_price: product.value.original_price,
    stock: product.value.stock,
    sort: product.value.sort || 0,
    category: product.value.category,
    recharge_hours: product.value.recharge_hours,
    bonus_hours: product.value.bonus_hours,
    tags: product.value.tags || [],
    is_active: product.value.is_active,
    is_hot: product.value.is_hot,
    is_new: product.value.is_new,
    discount_description: product.value.discount_description
  }
  editDialogVisible.value = true
}

const handleEditSubmit = async () => {
  await editFormRef.value.validate()

  editSubmitLoading.value = true
  try {
    await updateProduct(productId.value, editForm.value)
    ElMessage.success('更新成功')
    editDialogVisible.value = false
    fetchProductDetail()
  } catch (e) {
    // 错误已处理
  } finally {
    editSubmitLoading.value = false
  }
}

const resetEditForm = () => {
  editFormRef.value?.resetFields()
}

const handleToggleStatus = async () => {
  try {
    await toggleProductStatus(productId.value)
    ElMessage.success(product.value.is_active ? '已禁用' : '已启用')
    fetchProductDetail()
  } catch (e) {
    // 错误已处理
  }
}

const handleDelete = async () => {
  try {
    await ElMessageBox.confirm(`确定要删除产品 "${product.value?.name}" 吗？`, '提示', {
      type: 'warning'
    })
    await deleteProduct(productId.value)
    ElMessage.success('删除成功')
    router.push('/panel/product')
  } catch (e) {
    // 取消或错误
  }
}

onMounted(() => {
  fetchProductDetail()
  loadCategories()
})

const loadCategories = async () => {
  try {
    const res = await getCategoryOptions()
    categoryOptions.value = res.data
  } catch (e) {
    // 错误已处理
  }
}
</script>

<style lang="scss" scoped>
.product-detail {
  .detail-card {
    .card-header {
      display: flex;
      align-items: center;
      gap: 16px;

      .detail-title {
        font-size: 18px;
        font-weight: bold;
      }
    }
  }

  .loading-container {
    padding: 20px 0;
  }

  .detail-content {
    .detail-info {
      .product-name {
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 20px;
      }

      .info-item {
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;

        .info-label {
          font-weight: bold;
          color: #606266;
          min-width: 80px;
        }

        .info-value {
          color: #303133;

          &.price {
            font-size: 18px;
            font-weight: bold;
            color: #f56c6c;
          }
        }

        .tag-item {
          margin-right: 8px;
        }

        .no-tags {
          color: #909399;
        }
      }
    }

    .detail-section {
      margin-top: 30px;

      .section-title {
        font-size: 16px;
        font-weight: bold;
        margin-bottom: 16px;
        color: #303133;
      }

      .description {
        color: #606266;
        line-height: 1.8;
      }
    }

    .product-image {
      width: 200px;
      height: 200px;
      margin-right: 16px;
      margin-bottom: 16px;
      cursor: pointer;
    }

    .detail-actions {
      margin-top: 40px;
      display: flex;
      gap: 12px;
    }
  }
}
</style>


