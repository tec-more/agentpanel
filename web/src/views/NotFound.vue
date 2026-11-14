<template>
  <div class="not-found">
    <div class="content">
      <h1>404</h1>
      <p>抱歉，您访问的页面不存在</p>
      <el-button type="primary" @click="$router.push('/')">返回首页</el-button>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

// 兜底：无论因何种原因落到 404 页面，只要目标属于后台且当前未登录，
// 就直接送登录页。覆盖动态菜单路由尚未注册、bfcache 恢复的旧页面、
// 以及路由守卫被重定向打断等边缘情况，避免「未登录却看到 404 页面」。
// 已登录访问真正不存在的后台路径、以及非后台路径的 404 保持原样。
onMounted(() => {
  const path = route.path
  const isPanelPath = path === '/panel' || path.startsWith('/panel/')
  if (isPanelPath && path !== '/panel/login' && !localStorage.getItem('token')) {
    router.replace({ path: '/panel/login', query: { redirect: route.fullPath } })
  }
})
</script>

<style lang="scss" scoped>
.not-found {
  width: 100%;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);

  .content {
    text-align: center;

    h1 {
      font-size: 120px;
      font-weight: bold;
      color: #409eff;
      margin-bottom: 20px;
      text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.1);
    }

    p {
      font-size: 18px;
      color: #666;
      margin-bottom: 30px;
    }
  }
}
</style>


