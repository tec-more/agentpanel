<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="brand">
        <div class="brand-mark">C</div>
        <h1>客户中心</h1>
        <p>ContentOps 内容合规与自适应处理台</p>
      </div>

      <el-tabs v-model="mode" class="login-tabs">
        <el-tab-pane label="密码登录" name="password">
          <el-form :model="form" @keyup.enter="submit">
            <el-form-item>
              <el-input v-model="form.email" placeholder="邮箱" size="large" :prefix-icon="Message" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="form.password" type="password" placeholder="密码" size="large"
                :prefix-icon="Lock" show-password />
            </el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="验证码登录" name="code">
          <el-form>
            <el-form-item>
              <el-input v-model="form.email" placeholder="邮箱" size="large" :prefix-icon="Message" />
            </el-form-item>
            <el-form-item>
              <el-input v-model="form.code" placeholder="验证码" size="large" :prefix-icon="Lock">
                <template #append>
                  <el-button :loading="sending" :disabled="countdown > 0" @click="sendCode">
                    {{ countdown > 0 ? countdown + 's' : '获取验证码' }}
                  </el-button>
                </template>
              </el-input>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>

      <el-button type="primary" class="submit-btn" size="large" :loading="loading" @click="submit">
        登录
      </el-button>
      <div class="tip">客户账号由平台管理员开通，如需开通请联系客服。</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Message, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { apiSendCode, apiExchangeWebTicket } from '@/api'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const mode = ref('password')
const form = ref({ email: '', password: '', code: '' })
const loading = ref(false)
const sending = ref(false)
const countdown = ref(0)
let timer = null

/** 站内相对路径才允许作为票据登录后的落点，避免开放重定向。 */
function safeRedirect(value) {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//') && !value.includes('\\')
    ? value
    : '/dashboard'
}

/** dsh 免登入口：一次性票据换标准 Web 登录态，随后从 URL 清除票据。 */
async function consumeWebTicket() {
  const ticket = route.query.ticket
  if (typeof ticket !== 'string' || ticket.length < 32) return false
  loading.value = true
  try {
    const res = await apiExchangeWebTicket(ticket)
    auth._persist(res.data.access_token, res.data.customer)
    const redirect = safeRedirect(res.data.redirect_to || route.query.redirect)
    // replace 清除票据，避免浏览器历史 / Referer 泄漏。
    await router.replace({ path: redirect })
    ElMessage.success('登录成功')
    return true
  } catch (e) {
    await router.replace({ path: '/login' })
    return false
  } finally {
    loading.value = false
  }
}

onMounted(() => { void consumeWebTicket() })

async function sendCode() {
  if (!form.value.email) { ElMessage.warning('请先填写邮箱'); return }
  sending.value = true
  try {
    await apiSendCode({ email: form.value.email, type: 'login' })
    ElMessage.success('验证码已发送到邮箱')
    countdown.value = 60
    timer = setInterval(() => {
      countdown.value--
      if (countdown.value <= 0) clearInterval(timer)
    }, 1000)
  } catch (e) { /* 拦截器已提示 */ }
  finally { sending.value = false }
}

async function submit() {
  if (!form.value.email) { ElMessage.warning('请填写邮箱'); return }
  loading.value = true
  try {
    if (mode.value === 'password') {
      if (!form.value.password) { ElMessage.warning('请填写密码'); loading.value = false; return }
      await auth.loginByPassword(form.value.email, form.value.password)
    } else {
      if (!form.value.code) { ElMessage.warning('请填写验证码'); loading.value = false; return }
      await auth.loginByCode(form.value.email, form.value.code)
    }
    ElMessage.success('登录成功')
    router.push(route.query.redirect || '/dashboard')
  } catch (e) { /* 拦截器已提示 */ }
  finally { loading.value = false }
}

onUnmounted(() => timer && clearInterval(timer))
</script>

<style scoped>
.login-wrap {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1a6d4a 0%, #0f3d2c 100%);
}
.login-card {
  width: 400px;
  background: #fff;
  border-radius: 14px;
  padding: 36px 34px 28px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, .25);
}
.brand { text-align: center; margin-bottom: 22px; }
.brand-mark {
  width: 52px; height: 52px; margin: 0 auto 12px;
  border-radius: 14px;
  background: var(--cp-primary);
  color: #fff;
  font-size: 28px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}
.brand h1 { margin: 0 0 6px; font-size: 22px; }
.brand p { margin: 0; font-size: 13px; color: #8a94a6; }
.submit-btn { width: 100%; margin-top: 8px; }
.tip { text-align: center; font-size: 12px; color: #a0a8b5; margin-top: 16px; }
</style>
