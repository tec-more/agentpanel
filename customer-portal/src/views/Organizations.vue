<template>
  <el-card shadow="never">
    <template #header>我的组织</template>
    <el-table :data="items" v-loading="loading" size="small" style="width:100%">
      <el-table-column prop="org_id" label="组织ID" width="100" />
      <el-table-column prop="name" label="组织名称" />
      <el-table-column prop="my_role" label="我的角色" width="120">
        <template #default="{ row }">
          <el-tag :type="row.my_role === 'owner' ? 'success' : 'info'" size="small">{{ roleText(row.my_role) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="org_status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.org_status === 'active' ? 'success' : 'danger'" size="small">{{ row.org_status === 'active' ? '正常' : '停用' }}</el-tag>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="!loading && !items.length" description="你还没有加入任何组织" />
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiMyOrganizations } from '@/api'
const items = ref([])
const loading = ref(false)
const roleText = (r) => ({ owner: '所有者', admin: '管理员', member: '成员' }[r] || r)
onMounted(async () => {
  loading.value = true
  try { const res = await apiMyOrganizations(); items.value = res.data?.items || [] } catch (e) {}
  finally { loading.value = false }
})
</script>
