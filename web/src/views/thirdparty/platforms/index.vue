<template>
  <div class="thirdparty-platforms">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>平台管理</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            新增平台
          </el-button>
        </div>
      </template>
      <el-form :inline="true" :model="searchForm" class="mb-4">
        <el-form-item label="平台名称">
          <el-input v-model="searchForm.name" placeholder="请输入平台名称" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="resetForm">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>
      <el-table :data="platforms" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="平台名称" />
        <el-table-column prop="platform_type" label="平台类型" />
        <el-table-column prop="base_url" label="基础URL" />
        <el-table-column prop="status" label="状态">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'danger'">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="handleEdit(row)">
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            <el-button type="danger" size="small" @click="handleDelete(row.id)">
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
            <el-button size="small" @click="handleTest(row.id)">
              <el-icon><Connection /></el-icon>
              测试
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="mt-4">
        <el-pagination
          v-model:current-page="pageInfo.currentPage"
          v-model:page-size="pageInfo.pageSize"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="pageInfo.total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </el-card>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="600px"
    >
      <el-form :model="formData" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="平台名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入平台名称" />
        </el-form-item>
        <el-form-item label="平台类型" prop="platform_type">
          <el-select v-model="formData.platform_type" placeholder="请选择平台类型">
            <el-option label="SAAS" value="saas" />
            <el-option label="本地部署" value="local" />
          </el-select>
        </el-form-item>
        <el-form-item label="API密钥" prop="api_key">
          <el-input v-model="formData.api_key" placeholder="请输入API密钥" />
        </el-form-item>
        <el-form-item label="基础URL" prop="base_url">
          <el-input v-model="formData.base_url" placeholder="请输入平台基础URL" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="formData.status" placeholder="请选择状态">
            <el-option label="启用" value="active" />
            <el-option label="禁用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="formData.description" type="textarea" placeholder="请输入描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit">确定</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { Plus, Search, Refresh, Edit, Delete, Connection } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { getPlatforms, createPlatform, updatePlatform, deletePlatform, testPlatformConnection } from '@/api/thirdparty';

// 响应式数据
const platforms = ref([]);
const searchForm = reactive({
  name: ''
});
const pageInfo = reactive({
  currentPage: 1,
  pageSize: 10,
  total: 0
});
const dialogVisible = ref(false);
const dialogTitle = ref('新增平台');
const formData = reactive({
  name: '',
  platform_type: '',
  api_key: '',
  base_url: '',
  status: 'active',
  description: ''
});
const formRef = ref(null);
const rules = {
  name: [{ required: true, message: '请输入平台名称', trigger: 'blur' }],
  platform_type: [{ required: true, message: '请选择平台类型', trigger: 'change' }],
  api_key: [{ required: true, message: '请输入API密钥', trigger: 'blur' }],
  base_url: [{ required: true, message: '请输入基础URL', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }]
};

// 生命周期
onMounted(() => {
  fetchPlatforms();
});

// 方法
const fetchPlatforms = async () => {
  try {
    const response = await getPlatforms({
      skip: (pageInfo.currentPage - 1) * pageInfo.pageSize,
      limit: pageInfo.pageSize,
      ...searchForm
    });
    platforms.value = response.data;
    pageInfo.total = response.data.length; // 实际项目中应该从接口返回
  } catch (error) {
    ElMessage.error('获取平台列表失败');
    console.error(error);
  }
};

const handleSearch = () => {
  pageInfo.currentPage = 1;
  fetchPlatforms();
};

const resetForm = () => {
  searchForm.name = '';
  handleSearch();
};

const handleSizeChange = (size) => {
  pageInfo.pageSize = size;
  fetchPlatforms();
};

const handleCurrentChange = (current) => {
  pageInfo.currentPage = current;
  fetchPlatforms();
};

const handleAdd = () => {
  dialogTitle.value = '新增平台';
  Object.assign(formData, {
    name: '',
    platform_type: '',
    api_key: '',
    base_url: '',
    status: 'active',
    description: ''
  });
  dialogVisible.value = true;
};

const handleEdit = (row) => {
  dialogTitle.value = '编辑平台';
  Object.assign(formData, row);
  dialogVisible.value = true;
};

const handleSubmit = async () => {
  if (!formRef.value) return;
  await formRef.value.validate(async (valid) => {
    if (valid) {
      try {
        if (formData.id) {
          // 编辑
          await updatePlatform(formData.id, formData);
          ElMessage.success('编辑成功');
        } else {
          // 新增
          await createPlatform(formData);
          ElMessage.success('新增成功');
        }
        dialogVisible.value = false;
        fetchPlatforms();
      } catch (error) {
        ElMessage.error('操作失败');
        console.error(error);
      }
    }
  });
};

const handleDelete = async (id) => {
  try {
    await deletePlatform(id);
    ElMessage.success('删除成功');
    fetchPlatforms();
  } catch (error) {
    ElMessage.error('删除失败');
    console.error(error);
  }
};

const handleTest = async (id) => {
  try {
    const response = await testPlatformConnection(id);
    if (response.data.connected) {
      ElMessage.success('连接测试成功');
    } else {
      ElMessage.error('连接测试失败');
    }
  } catch (error) {
    ElMessage.error('测试失败');
    console.error(error);
  }
};
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mb-4 {
  margin-bottom: 16px;
}

.mt-4 {
  margin-top: 16px;
}

.dialog-footer {
  text-align: right;
}
</style>

