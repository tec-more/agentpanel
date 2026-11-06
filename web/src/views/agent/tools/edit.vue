<template>
    <div class="tool-edit">
        <el-card>
            <template #header>
                <div class="card-header">
                    <span>{{ isEdit ? '编辑工具' : '创建工具' }}</span>
                    <div class="button-group">
                        <el-button @click="goBack">
                            <el-icon><ArrowLeft /></el-icon>
                            返回
                        </el-button>
                        <el-button type="primary" @click="handleSubmit">
                            <el-icon><Check /></el-icon>
                            {{ isEdit ? '更新' : '创建' }}
                        </el-button>
                    </div>
                </div>
            </template>

            <el-form :model="form" ref="formRef" :rules="rules" label-width="120px" class="mt-4">
                <el-form-item label="工具标识" prop="name">
                    <el-input v-model="form.name" :disabled="isEdit" placeholder="请输入工具标识（英文）" />
                    <span v-if="isEdit" class="form-tip">工具标识创建后不可修改</span>
                </el-form-item>

                <el-form-item label="显示名称" prop="display_name">
                    <el-input v-model="form.display_name" placeholder="请输入显示名称" />
                </el-form-item>

                <el-form-item label="标签">
                    <el-select v-model="selectedTagIds" multiple placeholder="请选择标签" style="width: 100%">
                        <el-option v-for="tag in tags" :key="tag.id" :label="tag.name" :value="tag.id">
                            <div class="tag-option">
                                <el-tag size="medium">{{ tag.name }}</el-tag>
                            </div>
                        </el-option>
                    </el-select>
                </el-form-item>

                <el-form-item label="描述" prop="description">
                    <el-input type="textarea" v-model="form.description" placeholder="请输入工具描述" :rows="3" />
                </el-form-item>

                <el-form-item label="函数路径">
                    <el-input v-model="form.func_path" placeholder="如: tools.amazon.order_query" />
                    <span class="form-tip">Python函数路径，用于实际执行</span>
                </el-form-item>

                <el-form-item label="参数配置">
                    <div class="params-container">
                        <div v-if="form.parameters && form.parameters.length > 0">
                            <el-table :data="form.parameters" style="width: 100%" border>
                                <el-table-column label="参数名" width="150">
                                    <template #default="{ row }">
                                        <el-input v-model="row.name" size="small" placeholder="请输入参数名" />
                                    </template>
                                </el-table-column>
                                <el-table-column label="类型" width="100">
                                    <template #default="{ row }">
                                        <el-select v-model="row.type" size="small">
                                            <el-option label="string" value="string" />
                                            <el-option label="integer" value="integer" />
                                            <el-option label="number" value="number" />
                                            <el-option label="boolean" value="boolean" />
                                            <el-option label="date" value="date" />
                                            <el-option label="array" value="array" />
                                            <el-option label="object" value="object" />
                                        </el-select>
                                    </template>
                                </el-table-column>
                                <el-table-column label="必填" width="80">
                                    <template #default="{ row }">
                                        <el-switch v-model="row.required" />
                                    </template>
                                </el-table-column>
                                <el-table-column label="默认值" width="120">
                                    <template #default="{ row }">
                                        <el-input v-model="row.default" size="small" placeholder="默认值" />
                                    </template>
                                </el-table-column>
                                <el-table-column label="描述" min-width="150">
                                    <template #default="{ row }">
                                        <el-input v-model="row.description" size="small" placeholder="参数描述" />
                                    </template>
                                </el-table-column>
                                <el-table-column label="操作" width="80">
                                    <template #default="{ row, $index }">
                                        <el-button type="danger" size="small" @click="removeParam($index)">
                                            <el-icon><Delete /></el-icon>
                                        </el-button>
                                    </template>
                                </el-table-column>
                            </el-table>
                        </div>
                        <div v-else class="empty-params">
                            <p>暂无参数配置，点击下方按钮添加</p>
                        </div>
                        <el-button type="default" size="small" @click="addParam" class="mt-2">
                            <el-icon><Plus /></el-icon>
                            添加参数
                        </el-button>
                    </div>
                </el-form-item>

                <el-form-item label="状态">
                    <el-switch v-model="form.enabled" active-text="启用" inactive-text="禁用" />
                </el-form-item>
            </el-form>
        </el-card>
    </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ArrowLeft, Check, Plus, Delete } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { createTool, updateTool, getTool, getActiveToolTags } from '@/api/agent'

const router = useRouter()
const route = useRoute()
const formRef = ref(null)

const isEdit = computed(() => !!route.params.id)
const tags = ref([])
const selectedTagIds = ref([])

const form = reactive({
    name: '',
    display_name: '',
    description: '',
    func_path: '',
    parameters: [],
    enabled: true
})

const rules = {
    name: [
        { required: true, message: '请输入工具标识', trigger: 'blur' },
        { pattern: /^[a-zA-Z_][a-zA-Z0-9_]*$/, message: '工具标识只能包含字母、数字和下划线，且以字母或下划线开头', trigger: 'blur' }
    ],
    display_name: [
        { required: true, message: '请输入显示名称', trigger: 'blur' }
    ]
}

const addParam = () => {
    form.parameters.push({
        name: '',
        type: 'string',
        required: false,
        default: '',
        description: ''
    })
}

const removeParam = (index) => {
    form.parameters.splice(index, 1)
}

const goBack = () => {
    router.push('/panel/agent/tools')
}

const handleSubmit = async () => {
    if (!formRef.value) return
    
    try {
        await formRef.value.validate()
        
        const data = {
            name: form.name,
            display_name: form.display_name,
            description: form.description,
            func_path: form.func_path || null,
            parameters: form.parameters.length > 0 ? form.parameters : null,
            enabled: form.enabled,
            tag_ids: selectedTagIds.value.length > 0 ? selectedTagIds.value : null
        }

        if (isEdit.value) {
            await updateTool(route.params.id, data)
            ElMessage.success('工具更新成功')
        } else {
            await createTool(data)
            ElMessage.success('工具创建成功')
        }

        router.push('/panel/agent/tools')
    } catch (error) {
        console.error(error)
        ElMessage.error(isEdit.value ? '更新失败' : '创建失败')
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

const fetchTool = async () => {
    if (!isEdit.value) return
    
    try {
        const res = await getTool(route.params.id)
        if (res.data) {
            const tool = res.data
            form.name = tool.name
            form.display_name = tool.display_name
            form.description = tool.description || ''
            form.func_path = tool.func_path || ''
            form.parameters = tool.parameters || []
            form.enabled = tool.enabled
            
            selectedTagIds.value = tool.tags ? tool.tags.map(t => t.id) : []
        }
    } catch (error) {
        console.error('获取工具详情失败', error)
        ElMessage.error('获取工具详情失败')
    }
}

onMounted(() => {
    fetchTags()
    fetchTool()
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
.mt-4 {
    margin-top: 16px;
}
.form-tip {
    font-size: 12px;
    color: #999;
    margin-left: 8px;
}
.params-container {
    min-height: 100px;
}
.empty-params {
    text-align: center;
    padding: 20px;
    color: #999;
    background: #fafafa;
    border-radius: 4px;
}
.empty-params p {
    margin: 0;
}
.mt-2 {
    margin-top: 8px;
}
.tag-option {
    display: flex;
    align-items: center;
}
.el-select-dropdown__item{
    padding:5px;
}
</style>


