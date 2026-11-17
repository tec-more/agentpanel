<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="24">
        <el-card class="hero" shadow="never">
          <div class="hero-inner">
            <div>
              <h2>你好，{{ auth.displayName }}</h2>
              <p>欢迎使用客户内容工作台，在这里自助完成内容合规检测、查看会员与订单信息。</p>
            </div>
            <el-button type="primary" size="large" @click="$router.push('/check')">
              <el-icon><Search /></el-icon>&nbsp;开始合规检测
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="cards">
      <el-col :span="6" v-for="c in cards" :key="c.title">
        <el-card class="stat-card" shadow="hover" @click="$router.push(c.path)">
          <div class="stat-icon" :style="{ background: c.color }"><el-icon><component :is="c.icon" /></el-icon></div>
          <div class="stat-title">{{ c.title }}</div>
          <div class="stat-desc">{{ c.desc }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="24">
        <el-card shadow="never">
          <template #header><span>使用指引</span></template>
          <ol class="guide">
            <li>在「内容合规检测」粘贴待发布文案，系统按平台规则实时给出风险判定与修改建议。</li>
            <li>「合规规则」展示当前账号可见的检测规则，方便你理解判定依据。</li>
            <li>「我的会员 / 订单 / 支付记录」可查看你的权益与消费明细。</li>
          </ol>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
const cards = [
  { title: '内容合规检测', desc: '实时检测风险内容', icon: 'Search', color: '#1a6d4a', path: '/check' },
  { title: '合规规则', desc: '查看可见规则', icon: 'Document', color: '#3a7bd5', path: '/rules' },
  { title: '我的会员', desc: '等级与权益', icon: 'Medal', color: '#d68a1a', path: '/membership' },
  { title: '我的订单', desc: '消费与订单', icon: 'ShoppingBag', color: '#8e5ad6', path: '/orders' }
]
</script>

<style scoped>
.hero-inner { display: flex; align-items: center; justify-content: space-between; }
.hero h2 { margin: 0 0 8px; }
.hero p { margin: 0; color: #6b7280; }
.cards { margin: 16px 0; }
.stat-card { cursor: pointer; text-align: center; }
.stat-icon {
  width: 48px; height: 48px; border-radius: 12px; margin: 0 auto 12px;
  color: #fff; font-size: 24px; display: flex; align-items: center; justify-content: center;
}
.stat-title { font-weight: 600; }
.stat-desc { color: #9aa3af; font-size: 13px; margin-top: 4px; }
.guide { line-height: 2; color: #4b5563; margin: 0; padding-left: 20px; }
</style>
