<template>
  <div class="system-setting">
    <el-card shadow="never" class="action-card">
      <div class="action-bar">
        <el-button type="primary" :icon="Plus" @click="handleAdd">新增设置</el-button>
        <el-button :icon="Refresh" @click="handleInit">初始化默认设置</el-button>
        <el-button type="success" :icon="Check" @click="handleSave" :loading="submitLoading">保存设置</el-button>
      </div>
    </el-card>

    <el-card shadow="never" class="table-card">
      <el-table v-loading="loading" :data="tableData" border>
        <el-table-column prop="name" label="设置名称" width="180" />
        <el-table-column prop="key" label="设置键" width="180" />
        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="设置类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getSettingTypeTag(row.setting_type)" size="small">
              {{ getSettingTypeName(row.setting_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="设置值" min-width="300">
          <template #default="{ row }">
            <!-- 图片类型 -->
            <div v-if="row.setting_type === 'image'" class="setting-image">
              <el-input v-model="row.temp_value" placeholder="图片URL" style="flex: 1" />
              <el-upload
                class="image-uploader"
                :show-file-list="false"
                :on-success="(res) => handleImageUploadSuccess(res, row)"
                :before-upload="beforeImageUpload"
                :http-request="(options) => uploadImageAction(options, row)"
                accept="image/jpeg,image/png,image/gif,image/webp,image/bmp"
              >
                <el-button size="small" type="primary">上传</el-button>
              </el-upload>
              <el-image
                v-if="row.temp_value"
                :src="row.temp_value"
                :preview-src-list="[row.temp_value]"
                fit="cover"
                class="preview-image"
              />
            </div>
            <!-- 布尔类型 -->
            <div v-else-if="row.setting_type === 'boolean'" class="setting-boolean">
              <el-switch
                v-model="row.temp_value"
                :active-value="'true'"
                :inactive-value="'false'"
              />
            </div>
            <!-- 数字类型 -->
            <div v-else-if="row.setting_type === 'number'" class="setting-number">
              <el-input-number v-model="row.temp_value" :min="0" style="width: 100%" />
            </div>
            <!-- 文本类型（默认） -->
            <div v-else class="setting-text">
              <el-input v-model="row.temp_value" type="textarea" :rows="1" placeholder="请输入设置值" autosize />
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="sort" label="排序" width="80" align="center" />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '激活' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" align="center">
          <template #default="{ row }">
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
      width="500px"
      @close="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="设置名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入设置名称" />
        </el-form-item>
        <el-form-item label="设置键" prop="key">
          <el-input v-model="form.key" placeholder="请输入设置键" :disabled="isEdit" />
        </el-form-item>
        <el-form-item label="设置类型" prop="setting_type">
          <el-select v-model="form.setting_type" placeholder="请选择设置类型" style="width: 100%">
            <el-option label="文本" value="string" />
            <el-option label="数字" value="number" />
            <el-option label="布尔" value="boolean" />
            <el-option label="图片" value="image" />
          </el-select>
        </el-form-item>
        <el-form-item label="设置值" prop="value">
          <!-- 文本类型 -->
          <el-input v-if="form.setting_type === 'string'" v-model="form.value" type="textarea" :rows="2" placeholder="请输入设置值" />
          <!-- 数字类型 -->
          <el-input-number v-else-if="form.setting_type === 'number'" v-model="form.value" :min="0" style="width: 100%" />
          <!-- 布尔类型 -->
          <el-switch v-else-if="form.setting_type === 'boolean'" v-model="form.value" :active-value="true" :inactive-value="false" />
          <!-- 图片类型 -->
          <div v-else class="image-form-item">
            <el-input v-model="form.value" placeholder="图片URL" style="margin-bottom: 10px" />
            <el-upload
              class="image-uploader-inline"
              :show-file-list="false"
              :on-success="handleFormImageUploadSuccess"
              :before-upload="beforeImageUpload"
              :http-request="uploadFormImageAction"
              accept="image/jpeg,image/png,image/gif,image/webp,image/bmp"
            >
              <el-button size="small" type="primary">上传图片</el-button>
            </el-upload>
            <el-image
              v-if="form.value"
              :src="form.value"
              :preview-src-list="[form.value]"
              fit="cover"
              class="form-preview-image"
            />
          </div>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="请输入描述" />
        </el-form-item>
        <el-form-item label="排序" prop="sort">
          <el-input-number v-model="form.sort" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态" prop="is_active">
          <el-switch v-model="form.is_active" />
        </el-form-item>
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
import { Plus, Refresh, Check, Edit, Delete, Upload } from '@element-plus/icons-vue'
import {
  getSystemSettingList,
  createSystemSetting,
  updateSystemSetting,
  deleteSystemSetting,
  batchUpdateSystemSettings,
  initDefaultSettings
} from '@/api/systemSetting'
import { uploadImage } from '@/api/upload'

const loading = ref(false)
const submitLoading = ref(false)
const tableData = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)

const form = ref({
  name: '',
  key: '',
  value: '',
  description: '',
  setting_type: 'string',
  sort: 0,
  is_active: true
})

const rules = {
  name: [{ required: true, message: '请输入设置名称', trigger: 'blur' }],
  key: [{ required: true, message: '请输入设置键', trigger: 'blur' }],
  setting_type: [{ required: true, message: '请选择设置类型', trigger: 'change' }]
}

const dialogTitle = computed(() => isEdit.value ? '编辑设置' : '新增设置')

const getSettingTypeName = (type) => {
  const map = { string: '文本', number: '数字', boolean: '布尔', image: '图片' }
  return map[type] || type
}

const getSettingTypeTag = (type) => {
  const map = { string: '', number: 'primary', boolean: 'warning', image: 'success' }
  return map[type] || ''
}

const beforeImageUpload = (file) => {
  const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp']
  const isAllowed = allowedTypes.includes(file.type)
  if (!isAllowed) {
    ElMessage.error('只能上传 JPG、PNG、GIF、WebP、BMP 格式的图片!')
    return false
  }
  const isLt10M = file.size / 1024 / 1024 < 10
  if (!isLt10M) {
    ElMessage.error('图片大小不能超过 10MB!')
    return false
  }
  return true
}

const uploadImageAction = async (options, row) => {
  const { file } = options
  try {
    const res = await uploadImage(file)
    if (res.code === 0 || res.code === 200 || res.success) {
      row.temp_value = res.data.url
      ElMessage.success('上传成功')
    } else {
      ElMessage.error(res.msg || '上传失败')
    }
  } catch (error) {
    ElMessage.error('上传失败')
  }
}

const handleImageUploadSuccess = (response, row) => {
  if (response.code === 0 || response.code === 200 || response.success) {
    row.temp_value = response.data.url
    ElMessage.success('上传成功')
  }
}

const uploadFormImageAction = async (options) => {
  const { file } = options
  try {
    const res = await uploadImage(file)
    if (res.code === 0 || res.code === 200 || res.success) {
      form.value.value = res.data.url
      ElMessage.success('上传成功')
    } else {
      ElMessage.error(res.msg || '上传失败')
    }
  } catch (error) {
    ElMessage.error('上传失败')
  }
}

const handleFormImageUploadSuccess = (response) => {
  if (response.code === 0 || response.code === 200 || response.success) {
    form.value.value = response.data.url
    ElMessage.success('上传成功')
  }
}

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getSystemSettingList({ page_size: 100 })
    if (res.data && res.data.items) {
      tableData.value = res.data.items.map(item => ({
        ...item,
        temp_value: item.value || ''
      }))
    }
  } catch (e) {
    // 错误已处理
  } finally {
    loading.value = false
  }
}

const handleSave = async () => {
  try {
    await ElMessageBox.confirm('确定要保存所有修改的设置吗？', '提示', {
      type: 'warning'
    })
    
    const updateData = {}
    tableData.value.forEach(item => {
      updateData[item.key] = item.temp_value
    })
    
    submitLoading.value = true
    await batchUpdateSystemSettings(updateData)
    
    ElMessage.success('保存成功')
    fetchData()
  } catch (e) {
    // 取消或错误
  } finally {
    submitLoading.value = false
  }
}

const handleInit = async () => {
  try {
    await ElMessageBox.confirm('确定要初始化默认设置吗？这不会覆盖已有的设置。', '提示', {
      type: 'warning'
    })
    
    await initDefaultSettings()
    ElMessage.success('初始化成功')
    fetchData()
  } catch (e) {
    // 取消或错误
  }
}

const handleAdd = () => {
  isEdit.value = false
  form.value = {
    name: '',
    key: '',
    value: '',
    description: '',
    setting_type: 'string',
    sort: 0,
    is_active: true
  }
  dialogVisible.value = true
}

const handleEdit = (row) => {
  isEdit.value = true
  form.value = {
    id: row.id,
    name: row.name,
    key: row.key,
    value: row.value,
    description: row.description,
    setting_type: row.setting_type,
    sort: row.sort,
    is_active: row.is_active
  }
  dialogVisible.value = true
}

const handleSubmit = async () => {
  await formRef.value.validate()
  
  submitLoading.value = true
  try {
    if (isEdit.value) {
      await updateSystemSetting(form.value.id, form.value)
      ElMessage.success('更新成功')
    } else {
      await createSystemSetting(form.value)
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
    await ElMessageBox.confirm(`确定要删除设置 "${row.name}" 吗？`, '提示', {
      type: 'warning'
    })
    
    await deleteSystemSetting(row.id)
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
.system-setting {
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
  }

  .setting-image {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;

    .el-input {
      flex: 1;
    }

    .preview-image {
      width: 60px;
      height: 60px;
      border-radius: 4px;
      border: 1px solid #dcdfe6;
      cursor: pointer;
      flex-shrink: 0;
    }
  }

  .image-form-item {
    width: 100%;
    
    .form-preview-image {
      width: 100px;
      height: 100px;
      border-radius: 4px;
      border: 1px solid #dcdfe6;
      cursor: pointer;
      margin-top: 10px;
    }
  }
}
</style>


