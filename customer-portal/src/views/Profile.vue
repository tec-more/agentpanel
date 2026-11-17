<template>
  <el-card shadow="never" v-loading="loading">
    <template #header>我的资料</template>
    <el-descriptions :column="2" border v-if="profile">
      <el-descriptions-item label="客户ID">{{ profile.id }}</el-descriptions-item>
      <el-descriptions-item label="昵称">{{ profile.nickname || '—' }}</el-descriptions-item>
      <el-descriptions-item label="用户名">{{ profile.username || '—' }}</el-descriptions-item>
      <el-descriptions-item label="邮箱">{{ profile.email || '—' }}</el-descriptions-item>
      <el-descriptions-item label="手机号">{{ profile.phone || '—' }}</el-descriptions-item>
      <el-descriptions-item label="认证状态">
        <el-tag :type="profile.is_verified ? 'success' : 'warning'" size="small">{{ profile.is_verified ? '已认证' : '未认证' }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="账号状态">
        <el-tag :type="profile.is_active ? 'success' : 'danger'" size="small">{{ profile.is_active ? '正常' : '已禁用' }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="登录次数">{{ profile.login_count }}</el-descriptions-item>
      <el-descriptions-item label="注册时间">{{ profile.created_at }}</el-descriptions-item>
      <el-descriptions-item label="最后登录">{{ profile.last_login || '—' }}</el-descriptions-item>
    </el-descriptions>
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiMyProfile } from '@/api'
const profile = ref(null)
const loading = ref(false)
onMounted(async () => {
  loading.value = true
  try { const res = await apiMyProfile(); profile.value = res.data } catch (e) {}
  finally { loading.value = false }
})
</script>
