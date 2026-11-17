<template>
  <el-row :gutter="16" v-loading="loading">
    <el-col :span="12">
      <el-card shadow="never">
        <template #header>当前会员</template>
        <div class="level-head">
          <el-icon class="level-icon"><Medal /></el-icon>
          <div>
            <div class="level-name">{{ info?.level_name || '普通会员' }}</div>
            <div class="level-sub">{{ info?.is_vip ? 'VIP 会员' : info?.is_svip ? 'SVIP 会员' : '基础权益' }}</div>
          </div>
          <el-tag v-if="info?.is_expired" type="danger" class="expired">已过期</el-tag>
        </div>
        <el-descriptions :column="1" border class="info-table">
          <el-descriptions-item label="折扣">{{ info?.discount_percentage || 0 }}%</el-descriptions-item>
          <el-descriptions-item label="累计时长">{{ info?.total_hours || 0 }} 小时</el-descriptions-item>
          <el-descriptions-item label="剩余时长">{{ info?.remaining_hours ?? 0 }} 小时</el-descriptions-item>
          <el-descriptions-item label="到期时间">{{ info?.expire_time || '—' }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-col>
    <el-col :span="12">
      <el-card shadow="never">
        <template #header>会员等级说明</template>
        <el-timeline>
          <el-timeline-item v-for="l in levels" :key="l.level_type" :color="l.level_type === 'svip' ? '#d68a1a' : l.level_type === 'vip' ? '#3a7bd5' : '#909399'">
            <b>{{ l.name }}</b> — 累计 {{ l.hours }} 小时起
          </el-timeline-item>
        </el-timeline>
        <el-empty v-if="!levels.length" description="暂无等级配置" :image-size="50" />
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { apiMyMembership } from '@/api'
const info = ref(null)
// 等级说明为静态展示（累计时长对应的 Fibonacci 成长等级），非接口数据
const levels = ref([
  { level_type: 'regular', name: '普通会员', hours: 0 },
  { level_type: 'vip', name: 'VIP 会员', hours: 30 },
  { level_type: 'svip', name: 'SVIP 会员', hours: 100 }
])
const loading = ref(false)
onMounted(async () => {
  loading.value = true
  try { const res = await apiMyMembership(); info.value = res.data } catch (e) {}
  finally { loading.value = false }
})
</script>

<style scoped>
.level-head { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }
.level-icon { font-size: 40px; color: #d68a1a; }
.level-name { font-size: 20px; font-weight: 700; }
.level-sub { color: #8a94a6; font-size: 13px; }
.expired { margin-left: auto; }
</style>
