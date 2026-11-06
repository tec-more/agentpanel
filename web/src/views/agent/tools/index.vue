<template>
    <div class="tool-list">
        <el-card>
            <template #header>
                <div class="card-header">
                    <span>工具管理</span>
                    <div class="button-group">
                        <el-button type="default" @click="goToTags">
                            <el-icon><Folder /></el-icon>
                            工具标签
                        </el-button>
                        <el-button type="primary" @click="handleAdd">
                            <el-icon><Plus /></el-icon>
                            新增工具
                        </el-button>
                    </div>
                </div>
            </template>

            <el-form :inline="true" :model="searchForm" class="mb-4">
                <el-form-item label="工具名称">
                    <el-input v-model="searchForm.name" placeholder="请输入工具名称" clearable />
                </el-form-item>
                <el-form-item label="标签">
                    <el-select v-model="searchForm.tag_id" placeholder="请选择标签" clearable>
                        <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id">
                            <div class="tag-option">
                                <el-tag :color="tag.color" size="small">{{ tag.name }}</el-tag>
                            </div>
                        </el-option>
                    </el-select>
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

            <el-table :data="tools" style="width: 100%" v-loading="loading">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="name" label="工具标识" min-width="150" />
                <el-table-column prop="display_name" label="显示名称" min-width="120" />
                <el-table-column prop="tags" label="标签" width="200">
                    <template #default="{ row }">
                        <div v-if="row.tags && row.tags.length > 0" class="tool-tags">
                            <el-tag v-for="tag in row.tags" :key="tag.id" :color="tag.color" size="small" class="tool-tag">
                                {{ tag.name }}
                            </el-tag>
                        </div>
                        <span v-else class="text-gray">-</span>
                    </template>
                </el-table-column>
                <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />
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
    </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus, Search, Refresh, Edit, Delete, Folder } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTools, deleteTool, getActiveToolTags } from '@/api/agent'

const router = useRouter()
const loading = ref(false)
const tools = ref([])
const tags = ref([])

const searchForm = reactive({
    name: '',
    tag_id: null,
    enabled: null
})

const pageInfo = reactive({
    currentPage: 1,
    pageSize: 10,
    total: 0
})

const formatDate = (dateStr) => {
    if (!dateStr) return ''
    return new Date(dateStr).toLocaleString('zh-CN')
}

const fetchTools = async () => {
    loading.value = true
    try {
        const params = {
            skip: (pageInfo.currentPage - 1) * pageInfo.pageSize,
            limit: pageInfo.pageSize,
            name: searchForm.name || undefined,
            tag_id: searchForm.tag_id || undefined,
            enabled: searchForm.enabled
        }
        const res = await getTools(params)
        if (res.data) {
            tools.value = res.data.items || res.data
            pageInfo.total = res.data.total || tools.value.length
        }
    } catch (error) {
        ElMessage.error('获取工具列表失败')
        console.error(error)
    } finally {
        loading.value = false
    }
}

const fetchTags = async () => {
    try {
        const res = await getActiveToolTags()
        if (res.data) {
            tags.value = res.data
        }
    } catch (error) {
        console.error('获取标签列表失败', error)
    }
}

const handleSearch = () => {
    pageInfo.currentPage = 1
    fetchTools()
}

const resetSearch = () => {
    searchForm.name = ''
    searchForm.tag_id = null
    searchForm.enabled = null
    handleSearch()
}

const handleSizeChange = () => {
    fetchTools()
}

const handleCurrentChange = () => {
    fetchTools()
}

const handleAdd = () => {
    router.push('/panel/agent/tools/create')
}

const goToTags = () => {
    router.push('/panel/agent/tool-tags')
}

const handleEdit = (row) => {
    router.push(`/panel/agent/tools/edit/${row.id}`)
}

const handleDelete = async (id) => {
    try {
        await ElMessageBox.confirm('确定要删除该工具吗？', '提示', { type: 'warning' })
        await deleteTool(id)
        ElMessage.success('删除成功')
        fetchTools()
    } catch (error) {
        if (error !== 'cancel') {
            ElMessage.error('删除失败')
            console.error(error)
        }
    }
}

onMounted(() => {
    fetchTags()
    fetchTools()
})
</script>

<style scoped>
.card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.button-group {
    display: flex;
    gap: 8px;
}
.text-gray {
    color: #999;
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
.tool-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
}
.tool-tag {
    margin: 2px 0;
}
.tag-option {
    display: flex;
    align-items: center;
}
</style>


