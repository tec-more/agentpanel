<template>
    <div class="tool-tag-list">
        <el-card>
            <template #header>
                <div class="card-header">
                    <span>工具标签管理</span>
                    <el-button type="primary" @click="handleAdd">
                        <el-icon><Plus /></el-icon>
                        新增标签
                    </el-button>
                </div>
            </template>

            <el-form :inline="true" :model="searchForm" class="mb-4">
                <el-form-item label="标签名称">
                    <el-input v-model="searchForm.name" placeholder="请输入标签名称" clearable />
                </el-form-item>
                <el-form-item label="状态">
                    <el-select v-model="searchForm.enabled" placeholder="请选择状态" clearable>
                        <el-option label="启用" :value="true" />
                        <el-option label="禁用" :value="false" />
                    </el-select>
                </el-form-item>
                <el-form-item>
                    <el-button type="primary" @click="handleSearch">
                        <el-icon><Search /></el-icon>
                        搜索
                    </el-button>
                    <el-button @click="resetSearch">
                        <el-icon><Refresh /></el-icon>
                        重置
                    </el-button>
                </el-form-item>
            </el-form>

            <el-table :data="tags" style="width: 100%" v-loading="loading">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="name" label="标签名称" min-width="120">
                    <template #default="{ row }">
                        <el-tag>{{ row.name }}</el-tag>
                    </template>
                </el-table-column>
                <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
                <el-table-column prop="tool_count" label="工具数量" width="100" />
                <el-table-column prop="enabled" label="状态" width="100">
                    <template #default="{ row }">
                        <el-tag :type="row.enabled ? 'success' : 'danger'">
                            {{ row.enabled ? '启用' : '禁用' }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column prop="created_at" label="创建时间" width="180">
                    <template #default="{ row }">
                        {{ formatDate(row.created_at) }}
                    </template>
                </el-table-column>
                <el-table-column label="操作" width="200" fixed="right">
                    <template #default="{ row }">
                        <div class="action-buttons">
                            <el-button type="primary" size="small" @click="handleEdit(row)">
                                <el-icon><Edit /></el-icon>
                                编辑
                            </el-button>
                            <el-button type="danger" size="small" @click="handleDelete(row.id)">
                                <el-icon><Delete /></el-icon>
                                删除
                            </el-button>
                        </div>
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

        <!-- 编辑/新增对话框 -->
        <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑标签' : '新增标签'" width="500px">
            <el-form :model="form" ref="formRef" :rules="rules" label-width="100px">
                <el-form-item label="标签名称" prop="name">
                    <el-input v-model="form.name" placeholder="请输入标签名称" :disabled="isEdit" />
                </el-form-item>
                <el-form-item label="描述" prop="description">
                    <el-input v-model="form.description" type="textarea" placeholder="请输入描述" :rows="3" />
                </el-form-item>
                <el-form-item label="颜色" prop="color">
                    <el-color-picker v-model="form.color" />
                </el-form-item>
                <el-form-item label="排序" prop="sort_order">
                    <el-input-number v-model="form.sort_order" :min="0" />
                </el-form-item>
                <el-form-item label="状态">
                    <el-switch v-model="form.enabled" active-text="启用" inactive-text="禁用" />
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
import { useRouter } from 'vue-router'
import { Plus, Search, Refresh, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getToolTags, createToolTag, updateToolTag, deleteToolTag, getToolTagsWithCount } from '@/api/agent'

const router = useRouter()
const loading = ref(false)
const tags = ref([])
const dialogVisible = ref(false)
const isEdit = ref(false)
const currentId = ref(null)
const formRef = ref(null)

const searchForm = reactive({
    name: '',
    enabled: null
})

const pageInfo = reactive({
    currentPage: 1,
    pageSize: 10,
    total: 0
})

const form = reactive({
    name: '',
    description: '',
    color: '#409eff',
    sort_order: 0,
    enabled: true
})

const rules = {
    name: [{ required: true, message: '请输入标签名称', trigger: 'blur' }]
}

const formatDate = (dateStr) => {
    if (!dateStr) return ''
    return new Date(dateStr).toLocaleString('zh-CN')
}

const fetchTags = async () => {
    loading.value = true
    try {
        const res = await getToolTagsWithCount()
        if (res.data) {
            tags.value = res.data
            pageInfo.total = res.data.length
        }
    } catch (error) {
        ElMessage.error('获取标签列表失败')
        console.error(error)
    } finally {
        loading.value = false
    }
}

const handleSearch = () => {
    pageInfo.currentPage = 1
    fetchTags()
}

const resetSearch = () => {
    searchForm.name = ''
    searchForm.enabled = null
    handleSearch()
}

const handleSizeChange = () => {
    fetchTags()
}

const handleCurrentChange = () => {
    fetchTags()
}

const handleAdd = () => {
    isEdit.value = false
    currentId.value = null
    form.name = ''
    form.description = ''
    form.color = '#409eff'
    form.sort_order = 0
    form.enabled = true
    dialogVisible.value = true
}

const handleEdit = (row) => {
    isEdit.value = true
    currentId.value = row.id
    form.name = row.name
    form.description = row.description
    form.color = row.color
    form.sort_order = row.sort_order
    form.enabled = row.enabled
    dialogVisible.value = true
}

const handleSubmit = async () => {
    if (!formRef.value) return
    await formRef.value.validate()
    
    try {
        if (isEdit.value) {
            await updateToolTag(currentId.value, form)
            ElMessage.success('更新成功')
        } else {
            await createToolTag(form)
            ElMessage.success('创建成功')
        }
        dialogVisible.value = false
        fetchTags()
    } catch (error) {
        ElMessage.error('操作失败')
        console.error(error)
    }
}

const handleDelete = async (id) => {
    try {
        await ElMessageBox.confirm('确定要删除该标签吗？', '提示', { type: 'warning' })
        await deleteToolTag(id)
        ElMessage.success('删除成功')
        fetchTags()
    } catch (error) {
        if (error !== 'cancel') {
            ElMessage.error('删除失败')
            console.error(error)
        }
    }
}

onMounted(() => {
    fetchTags()
})
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
.action-buttons {
    display: flex;
    justify-content: flex-start;
    align-items: center;
    gap: 4px;
}
</style>


