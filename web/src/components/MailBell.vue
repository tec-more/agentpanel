<template>
  <el-popover v-model:visible="popoverVisible" trigger="click" width="380" placement="bottom-end" popper-class="mail-bell-popover">
    <template #reference>
      <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99" class="bell-badge">
        <el-icon class="bell-icon"><Bell /></el-icon>
      </el-badge>
    </template>

    <div class="mail-popover">
      <div class="popover-header">
        <span class="popover-title">通知</span>
        <el-button v-if="unreadCount > 0" link type="primary" @click="markAllRead">全部已读</el-button>
      </div>

      <div v-loading="loading" class="popover-list">
        <div
          v-for="n in recentList"
          :key="n.id"
          class="popover-item"
          :class="{ unread: !n.is_read }"
          @click="handleClickItem(n)"
        >
          <el-icon v-if="n.is_starred" class="star-icon"><Star /></el-icon>
          <div class="item-content">
            <div class="item-title">
              {{ n.message?.subject || n.message?.record_name || '系统通知' }}
            </div>
            <div class="item-body">{{ stripHtml(n.message?.body) }}</div>
            <div class="item-meta">
              <el-tag size="small" :type="typeTagType(n.message?.message_type)">
                {{ typeLabel(n.message?.message_type) }}
              </el-tag>
              <span class="item-time">{{ n.created_at }}</span>
            </div>
          </div>
        </div>
        <el-empty v-if="!recentList.length && !loading" description="暂无通知" :image-size="60" />
      </div>

      <div class="popover-footer">
        <el-button type="primary" link @click="goInbox">查看全部</el-button>
      </div>
    </div>
  </el-popover>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElNotification } from 'element-plus'
import { Bell, Star } from '@element-plus/icons-vue'
import { getInbox, getUnreadCount, markRead } from '@/api/mail'
import { useSystemStore } from '@/stores/system'
import { wsUrl } from '@/utils/apiBase'

const router = useRouter()
const system = useSystemStore()

const unreadCount = ref(0)
const recentList = ref([])
const loading = ref(false)
const popoverVisible = ref(false)
// 接口 404 说明插件路由未装配（例如启动期 DB 抖动导致启用中断），
// 此时停止轮询与 WS 重连，避免每 30s 刷一条 404。
const mailUnavailable = ref(false)

let ws = null
let shouldReconnect = false
let pollTimer = null
let pollAbort = null

const stripHtml = (html) => {
  if (!html) return ''
  return html.replace(/<[^>]+>/g, '').slice(0, 80)
}

const typeTagType = (t) => {
  if (t === 'comment') return 'success'
  if (t === 'email') return 'warning'
  return 'info'
}

const typeLabel = (t) => {
  if (t === 'comment') return '评论'
  if (t === 'email') return '邮件'
  if (t === 'notification') return '通知'
  return t || '-'
}

const stopPolling = () => {
  shouldReconnect = false
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  // 取消已发出但尚未返回的未读数请求，避免退出时残留一条 401
  if (pollAbort) {
    try { pollAbort.abort() } catch (e) {}
    pollAbort = null
  }
  if (ws) {
    try { ws.close() } catch (e) {}
    ws = null
  }
}

const markUnavailable = () => {
  mailUnavailable.value = true
  stopPolling()
}

const fetchUnread = async () => {
  if (mailUnavailable.value) return
  const controller = new AbortController()
  pollAbort = controller
  try {
    const res = await getUnreadCount({ signal: controller.signal })
    unreadCount.value = res.data?.unread_count || 0
  } catch (e) {
    // 退出登录时主动取消的在途请求不算失败，也不会留下 401
    if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError') return
    const status = e?.response?.status
    // 401 表示登录态已失效；404 表示插件路由不可用，两者都停止无效请求
    if (status === 401) {
      stopPolling()
    } else if (status === 404) {
      markUnavailable()
    }
    // 其他错误静默处理
  } finally {
    if (pollAbort === controller) pollAbort = null
  }
}

const fetchRecent = async () => {
  if (mailUnavailable.value) return
  loading.value = true
  try {
    const res = await getInbox({ page: 1, page_size: 5, is_read: false }, { silent: true })
    recentList.value = res.data?.items || []
  } catch (e) {
    if (e?.response?.status === 404) markUnavailable()
    // 静默失败
  } finally {
    loading.value = false
  }
}

const connectWs = () => {
  const token = localStorage.getItem('token')
  if (!token || mailUnavailable.value) return

  const url = `${wsUrl('/v1/mail/ws')}?token=${encodeURIComponent(token)}`

  try {
    ws = new WebSocket(url)
  } catch (e) {
    console.warn('[mail.ws] 连接失败', e)
    return
  }

  ws.onopen = () => {
    shouldReconnect = true
  }

  ws.onmessage = (e) => {
    try {
      const data = JSON.parse(e.data)
      if (data.type === 'notification') {
        unreadCount.value = data.unread_count ?? (unreadCount.value + 1)
        // 用 notification 中的字段，回退到 message
        const msg = data.message || data.notification?.message || {}
        recentList.value.unshift(data.notification || msg)
        if (recentList.value.length > 5) recentList.value.pop()
        ElNotification({
          title: msg.subject || msg.record_name || '新消息',
          message: stripHtml(msg.body),
          type: 'info',
          duration: 4000
        })
      } else if (data.type === 'unread_count') {
        unreadCount.value = data.unread_count || 0
      }
    } catch (err) {
      console.warn('[mail.ws] 消息解析失败', err)
    }
  }

  ws.onclose = () => {
    ws = null
    if (shouldReconnect && !mailUnavailable.value) {
      setTimeout(connectWs, 3000)
    }
  }

  ws.onerror = () => {
    // 由 onclose 兜底重连
  }
}

const handleClickItem = async (n) => {
  if (!n.is_read) {
    try {
      await markRead([n.id])
      n.is_read = true
      unreadCount.value = Math.max(0, unreadCount.value - 1)
    } catch (e) {
      // 忽略
    }
  }
  popoverVisible.value = false
  // 后续可按 model/res_id 跳转到业务记录详情，本期仅关闭 popover
}

const markAllRead = async () => {
  try {
    await markRead([])
    unreadCount.value = 0
    recentList.value = []
    ElMessage.success('已全部标记为已读')
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

const goInbox = () => {
  popoverVisible.value = false
  router.push('/panel/mail/inbox')
}

const onRefreshEvent = () => {
  if (mailUnavailable.value) return
  fetchUnread()
  fetchRecent()
}

// 退出登录时立即停掉轮询 / WS 重连，避免组件尚未卸载期间用失效 token 刷 401
const onAppLogout = () => stopPolling()

onMounted(() => {
  // mail 插件未启用时不轮询/不连 WS，避免 404
  if (!system.isPluginEnabled('mail')) return
  fetchUnread()
  fetchRecent()
  connectWs()
  pollTimer = setInterval(fetchUnread, 30000)
  window.addEventListener('mail:refresh', onRefreshEvent)
  window.addEventListener('app:logout', onAppLogout)
})

onUnmounted(() => {
  stopPolling()
  window.removeEventListener('mail:refresh', onRefreshEvent)
  window.removeEventListener('app:logout', onAppLogout)
})
</script>

<style scoped>
.bell-badge {
  display: inline-flex;
  align-items: center;
}
.bell-icon {
  font-size: 20px;
  color: #bfcbd9;
  cursor: pointer;
  transition: color 0.2s;
}
.bell-icon:hover {
  color: #409eff;
}
.mail-popover {
  margin: -12px;
}
.popover-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid #ebeef5;
}
.popover-title {
  font-weight: 600;
  color: #303133;
}
.popover-list {
  max-height: 360px;
  overflow-y: auto;
}
.popover-item {
  display: flex;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid #f0f2f5;
  cursor: pointer;
  transition: background 0.2s;
}
.popover-item:hover {
  background: #f5f7fa;
}
.popover-item.unread {
  background: #ecf5ff;
}
.popover-item.unread:hover {
  background: #e1f0ff;
}
.star-icon {
  color: #e6a23c;
  margin-top: 2px;
}
.item-content {
  flex: 1;
  min-width: 0;
}
.item-title {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-body {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.item-time {
  font-size: 11px;
  color: #c0c4cc;
}
.popover-footer {
  text-align: center;
  padding: 8px 14px;
  border-top: 1px solid #ebeef5;
}
</style>
