<template>
  <el-card shadow="never">
    <template #header>
      <div class="card-head">
        <span>我可见的合规规则</span>
        <el-select v-model="layer" clearable placeholder="全部层级" size="small" style="width:140px" @change="load">
          <el-option v-for="l in ['L1','L2','L3','L4']" :key="l" :label="l" :value="l" />
        </el-select>
      </div>
    </template>
    <el-table :data="items" v-loading="loading" size="small" style="width:100%">
      <el-table-column prop="layer" label="层级" width="70" />
      <el-table-column prop="type" label="类型" width="90" />
      <el-table-column prop="risk_level" label="风险" width="80">
        <template #default="{ row }">
          <el-tag :type="row.risk_level === 'P0' ? 'danger' : row.risk_level === 'P1' ? 'warning' : 'info'" size="small">{{ row.risk_level }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="category" label="分类" width="120" />
      <el-table-column prop="pattern" label="规则表达式" show-overflow-tooltip />
      <el-table-column prop="suggestion" label="建议" show-overflow-tooltip />
    </el-table>
    <el-empty v-if="!loading && !items.length" description="暂无可见规则" />
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiWorkspaceRules } from '@/api'
const layer = ref(null)
const items = ref([])
const loading = ref(false)
async function load() {
  loading.value = true
  try {
    const res = await apiWorkspaceRules({ layer: layer.value || undefined })
    items.value = res.data?.items || []
  } catch (e) {} finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.card-head { display: flex; align-items: center; justify-content: space-between; }
</style>
