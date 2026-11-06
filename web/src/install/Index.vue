<template>
  <div class="install-container">
    <div class="install-card">
      <!-- 头部 -->
      <div class="install-header">
        <h1 class="install-title">
          <el-icon class="title-icon"><Setting /></el-icon>
          {{ systemStore.backend_name || '系统' }} 安装向导
        </h1>
        <p class="install-desc">欢迎使用 {{ systemStore.backend_name || '本系统' }}，请按照以下步骤完成系统安装</p>
      </div>

      <!-- 步骤指示器 -->
      <el-steps
        :active="currentStep"
        :process-status="stepStatus"
        :finish-status="'success'"
        align-center
        class="install-steps"
      >
        <el-step title="环境检测" :icon="Monitor" />
        <el-step title="数据库配置" :icon="Coin" />
        <el-step title="管理员设置" :icon="User" />
        <el-step title="完成安装" :icon="CircleCheck" />
      </el-steps>

      <!-- 步骤内容 -->
      <div class="install-content">
        <!-- 第一步：环境检测 -->
        <div v-if="currentStep === 0" class="step-content">
          <el-card class="env-check-card">
            <template #header>
              <div class="card-header">
                <el-icon><Monitor /></el-icon>
                <span>环境检测</span>
              </div>
            </template>
            <div class="env-items" v-loading="envChecking" element-loading-text="正在检测环境...">
              <div class="env-item" v-for="item in envChecks" :key="item.name">
                <span class="env-name">{{ item.name }}</span>
                <span class="env-value" :class="item.status">
                  <el-icon v-if="item.status === 'success'"><CircleCheck /></el-icon>
                  <el-icon v-else-if="item.status === 'warning'"><Warning /></el-icon>
                  <el-icon v-else><CircleClose /></el-icon>
                  {{ item.value }}
                </span>
                <span class="env-desc">{{ item.desc }}</span>
              </div>
              <el-empty v-if="!envChecking && envChecks.length === 0" description="暂无检测数据" />
            </div>
            <div class="env-actions" v-if="!envChecking">
              <el-button size="small" @click="doEnvCheck">
                <el-icon><Refresh /></el-icon>
                重新检测
              </el-button>
            </div>
          </el-card>
          <div class="step-actions">
            <el-button type="primary" :disabled="!envReady" @click="nextStep">
              下一步：配置数据库
              <el-icon style="margin-left: 4px;"><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>

        <!-- 第二步：数据库配置 -->
        <div v-if="currentStep === 1" class="step-content">
          <el-form
            ref="dbFormRef"
            :model="dbForm"
            :rules="dbRules"
            label-width="120px"
            class="db-form"
          >
            <el-form-item label="数据库类型">
              <el-select v-model="dbForm.db_type" disabled>
                <el-option label="PostgreSQL / openGauss" value="postgresql" />
              </el-select>
            </el-form-item>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="主机地址" prop="db_host">
                  <el-input v-model="dbForm.db_host" placeholder="127.0.0.1" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="端口" prop="db_port">
                  <el-input v-model.number="dbForm.db_port" placeholder="15432" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="数据库名" prop="db_name">
                  <el-input v-model="dbForm.db_name" placeholder="aipaneladmin" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="用户名" prop="db_user">
                  <el-input v-model="dbForm.db_user" placeholder="admin" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-form-item label="密码" prop="db_password">
              <el-input v-model="dbForm.db_password" type="password" show-password placeholder="请输入数据库密码" />
            </el-form-item>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="字符集">
                  <el-select v-model="dbForm.charset" placeholder="请选择字符集">
                    <el-option label="UTF8 (推荐)" value="UTF8" />
                    <el-option label="GBK" value="GBK" />
                    <el-option label="GB18030" value="GB18030" />
                    <el-option label="LATIN1" value="LATIN1" />
                    <el-option label="SQL_ASCII" value="SQL_ASCII" />
                  </el-select>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label=" " label-width="1px">
                  <div class="auto-create-wrapper">
                    <el-checkbox v-model="dbForm.auto_create_db">
                      <span>自动创建数据库（如果指定的数据库不存在）</span>
                    </el-checkbox>
                    <el-tooltip content="需要数据库用户具有 CREATE DATABASE 权限" placement="top">
                      <el-icon class="help-icon"><QuestionFilled /></el-icon>
                    </el-tooltip>
                  </div>
                </el-form-item>
              </el-col>
            </el-row>
            <el-divider content-position="left">连接池配置（可选）</el-divider>
            <el-row :gutter="20">
              <el-col :span="8">
                <el-form-item label="最小连接">
                  <el-input v-model.number="dbForm.minsize" type="number" min="1" max="50" placeholder="5" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="最大连接">
                  <el-input v-model.number="dbForm.maxsize" type="number" min="1" max="200" placeholder="20" />
                </el-form-item>
              </el-col>
              <el-col :span="8">
                <el-form-item label="超时时间(秒)">
                  <el-input v-model.number="dbForm.timeout" type="number" min="5" max="300" placeholder="30" />
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
          <!-- 非空数据库警告 -->
          <el-alert
            v-if="databaseNotEmptyWarning"
            title="当前数据库不为空，无法安装！"
            type="error"
            :closable="false"
            show-icon
            class="empty-db-alert"
          >
            <template #default>
              <div class="alert-body">
                <p>
                  检测到该数据库中已存在
                  <strong>{{ testResult?.table_count ?? 0 }}</strong>
                  张表，可能包含旧数据或业务数据。
                </p>
                <p class="alert-actions">
                  <el-icon><WarningFilled /></el-icon>
                  为避免数据丢失，<strong>系统禁止在非空数据库上强制安装</strong>。
                  请执行以下任一操作：
                </p>
                <ul class="alert-suggestions">
                  <li>① 修改「数据库名」，填写一个不存在的新库名，并勾选「自动创建数据库」</li>
                  <li>② 使用 DBA 工具手动清空当前数据库（删除 public schema 下的所有用户表）</li>
                  <li>③ 连接到另一个空的数据库实例</li>
                </ul>
              </div>
            </template>
          </el-alert>

          <div class="db-test-section">
            <el-button
              type="success"
              :loading="testingConnection"
              @click="handleTestConnection"
            >
              <el-icon><Connection /></el-icon>
              测试连接
            </el-button>
            <span
              v-if="testResult"
              class="test-result"
              :class="testResult.success ? 'success' : 'error'"
            >
              <el-icon v-if="testResult.success"><CircleCheck /></el-icon>
              <el-icon v-else><CircleClose /></el-icon>
              {{ testResult.message }}
              <span v-if="testResult.response_time_ms" class="response-time">
                ({{ testResult.response_time_ms }}ms)
              </span>
              <span
                v-if="testResult.table_count !== undefined && testResult.table_count >= 0"
                class="table-count-tag"
              >
                表数量: {{ testResult.table_count }}
              </span>
            </span>
          </div>
          <div class="step-actions">
            <el-button @click="prevStep">
              <el-icon><ArrowLeft /></el-icon>
              上一步
            </el-button>
            <el-button
              type="primary"
              :disabled="!dbConnectionOk"
              @click="nextStep"
            >
              下一步：设置管理员
              <el-icon style="margin-left: 4px;"><ArrowRight /></el-icon>
            </el-button>
          </div>
        </div>

        <!-- 第三步：管理员设置 -->
        <div v-if="currentStep === 2" class="step-content">
          <el-form
            ref="adminFormRef"
            :model="adminForm"
            :rules="adminRules"
            label-width="120px"
            class="admin-form"
          >
            <el-divider content-position="left">管理员账户</el-divider>
            <el-form-item label="用户名" prop="username">
              <el-input v-model="adminForm.username" placeholder="admin" maxlength="20" />
              <div class="form-tip">管理员登录用户名，建议使用英文字母和数字</div>
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input v-model="adminForm.password" type="password" show-password placeholder="至少8位字符" />
              <div class="form-tip">密码强度：至少8位，建议包含大小写字母、数字和特殊字符</div>
            </el-form-item>
            <el-form-item label="确认密码" prop="confirmPassword">
              <el-input v-model="adminForm.confirmPassword" type="password" show-password placeholder="再次输入密码" />
            </el-form-item>
            <el-divider content-position="left">基本信息</el-divider>
            <el-form-item label="昵称">
              <el-input v-model="adminForm.alias" placeholder="系统管理员" />
            </el-form-item>
            <el-form-item label="邮箱" prop="email">
              <el-input v-model="adminForm.email" placeholder="admin@example.com" />
            </el-form-item>
            <el-divider content-position="left">服务器配置</el-divider>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="访问端口">
                  <el-input-number v-model="serverForm.app_port" :min="1" :max="65535" />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="调试模式">
                  <el-switch v-model="serverForm.app_debug" active-text="开启" inactive-text="关闭" />
                </el-form-item>
              </el-col>
            </el-row>
            <el-divider content-position="left">系统名称</el-divider>
            <el-row :gutter="20">
              <el-col :span="12">
                <el-form-item label="前端名称">
                  <el-input v-model="serverForm.frontend_name" placeholder="" maxlength="50" />
                  <div class="form-tip">前端展示的系统名称</div>
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="后台名称">
                  <el-input v-model="serverForm.backend_name" placeholder="" maxlength="50" />
                  <div class="form-tip">后台登录页显示的名称</div>
                </el-form-item>
              </el-col>
            </el-row>
          </el-form>
          <div class="step-actions">
            <el-button @click="prevStep">
              <el-icon><ArrowLeft /></el-icon>
              上一步
            </el-button>
            <el-button
              type="primary"
              :disabled="!adminFormValid"
              :loading="installing"
              @click="handleExecuteInstall"
            >
              <el-icon><Download /></el-icon>
              {{ installing ? '安装中...' : '开始安装' }}
            </el-button>
          </div>
        </div>

        <!-- 第四步：安装进度 -->
        <div v-if="currentStep === 3" class="step-content">
          <div class="install-progress">
            <el-progress
              :percentage="installProgress"
              :status="installStatus"
              :stroke-width="20"
              :text-inside="true"
            />
            <div class="install-logs">
              <div v-for="(log, index) in installLogs" :key="index" class="log-item" :class="log.type">
                <el-icon v-if="log.type === 'success'"><CircleCheck /></el-icon>
                <el-icon v-else-if="log.type === 'error'"><CircleClose /></el-icon>
                <el-icon v-else><Loading /></el-icon>
                <span>{{ log.message }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 第五步：安装完成 -->
        <div v-if="currentStep === 4" class="step-content">
          <el-result
            icon="success"
            title="安装成功"
            sub-title="系统基础配置已完成，数据库和表结构已就绪"
          >
            <template #extra>
              <div class="install-result-info">
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="管理员用户名">{{ installResult?.admin_username }}</el-descriptions-item>
                  <el-descriptions-item label="管理员邮箱">{{ installResult?.admin_email }}</el-descriptions-item>
                </el-descriptions>

                <!-- 手动重启提示 -->
                <el-alert
                  type="warning"
                  :closable="false"
                  show-icon
                  class="restart-required-alert"
                >
                  <template #title>
                    <span class="restart-alert-title">
                      <el-icon><WarningFilled /></el-icon>
                      必须手动重启应用服务
                    </span>
                  </template>
                  <template #default>
                    <div class="restart-alert-body">
                      <p>为使数据库连接池配置、系统名称等新配置生效，必须重启应用服务。</p>
                    </div>
                  </template>
                </el-alert>

                <p class="warning-text">
                  <el-icon><Warning /></el-icon>
                  请妥善保管管理员账户信息，建议登录后立即修改默认密码。
                </p>
              </div>
              <el-button
                type="primary"
                size="large"
                :disabled="!restartConfirmed"
                @click="goToLogin"
              >
                我已重启，前往登录
                <el-icon style="margin-left: 4px;"><ArrowRight /></el-icon>
              </el-button>
              <el-checkbox
                v-model="restartConfirmed"
                class="restart-confirm-checkbox"
              >
                确认已手动重启应用服务
              </el-checkbox>
            </template>
          </el-result>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Setting, Monitor, Coin, User, CircleCheck, CircleClose,
  Warning, WarningFilled, ArrowRight, ArrowLeft, Connection, Download,
  Loading, QuestionFilled, Refresh
} from '@element-plus/icons-vue'
import { getInstallStatus, testDatabaseConnection, executeInstallation, envCheck } from '@/api/install'
import { useSystemStore } from '@/stores/system'

const router = useRouter()
const systemStore = useSystemStore()

// 当前步骤
const currentStep = ref(0)
const installReady = ref(false)

// 环境检测加载中
const envChecking = ref(true)

// 步骤状态：让已完成步骤显示 success，当前步骤显示 process
const stepStatus = computed(() => {
  if (installing.value) return 'process'
  if (installStatus.value === 'success') return 'success'
  return 'process'
})

// 环境检测（动态获取）
const envChecks = ref([])

const envReady = computed(() => {
  return envChecks.value.length > 0 && envChecks.value.every(item => item.status !== 'error')
})

// 数据库表单
const dbFormRef = ref(null)
const dbForm = reactive({
  db_type: 'postgresql',
  db_host: '127.0.0.1',
  db_port: 15432,
  db_name: 'aipaneladmin',
  db_user: 'admin',
  db_password: '',
  charset: 'UTF8',
  minsize: 5,
  maxsize: 20,
  timeout: 30,
  auto_create_db: false
})

const dbRules = {
  db_host: [{ required: true, message: '请输入数据库主机地址', trigger: 'blur' }],
  db_port: [{ required: true, message: '请输入端口', trigger: 'blur' }],
  db_name: [{ required: true, message: '请输入数据库名', trigger: 'blur' }],
  db_user: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  db_password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const testingConnection = ref(false)
const testResult = ref(null)
const dbConnectionOk = ref(false)
// 数据库非空警告标记：连接成功但 is_empty=false 时显示
const databaseNotEmptyWarning = ref(false)

// 管理员表单
const adminFormRef = ref(null)
const adminForm = reactive({
  username: 'admin',
  password: '',
  confirmPassword: '',
  email: '',
  alias: '系统管理员'
})

const adminRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度为 3-20 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少 8 位字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== adminForm.password) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ],
  email: [
    { type: 'email', message: '请输入正确的邮箱地址', trigger: ['blur', 'change'] }
  ]
}

const serverForm = reactive({
  app_port: 9998,
  app_debug: false,
  frontend_name: '',
  backend_name: ''
})

const adminFormValid = ref(false)

// 安装进度
const installing = ref(false)
const installProgress = ref(0)
const installStatus = ref('')
const installLogs = ref([])
const installResult = ref(null)
let installTimer = null

// 安装完成页 - 用户确认已重启应用
const restartConfirmed = ref(false)

// 监听步骤变化，实现"进入步骤即激活"
watch(currentStep, async (newStep, oldStep) => {
  if (newStep === 0 && oldStep !== undefined) {
    // 从其他步骤退回环境检测时，重新执行检测
    await doEnvCheck()
  } else if (newStep === 1) {
    // 进入数据库配置步骤：重置连接状态（防止"上一次连接通过"残留）
    dbConnectionOk.value = false
    databaseNotEmptyWarning.value = false
    testResult.value = null
  } else if (newStep === 2) {
    // 进入管理员设置步骤：触发表单初始验证（让"开始安装"按钮即时可判断）
    nextTick(() => {
      if (adminFormRef.value) {
        adminFormRef.value.validate((valid) => {
          adminFormValid.value = valid
        })
      }
    })
  }
})

// 下一步
const nextStep = async () => {
  if (currentStep.value === 0) {
    currentStep.value = 1
  } else if (currentStep.value === 1) {
    await dbFormRef.value.validate()
    if (!dbConnectionOk.value) {
      ElMessage.warning('请先测试数据库连接')
      return
    }
    currentStep.value = 2
  }
}

// 上一步
const prevStep = () => {
  if (currentStep.value > 0 && currentStep.value < 3) {
    currentStep.value--
  }
}

// 测试数据库连接
const handleTestConnection = async () => {
  testingConnection.value = true
  testResult.value = null
  dbConnectionOk.value = false
  databaseNotEmptyWarning.value = false

  try {
    const res = await testDatabaseConnection({
      database: {
        db_host: dbForm.db_host,
        db_port: dbForm.db_port,
        db_name: dbForm.db_name,
        db_user: dbForm.db_user,
        db_password: dbForm.db_password,
        charset: dbForm.charset,
        minsize: dbForm.minsize,
        maxsize: dbForm.maxsize,
        timeout: dbForm.timeout,
        command_timeout: dbForm.timeout,
        auto_create_db: dbForm.auto_create_db
      }
    })

    // 兼容不同的响应格式
    const data = res.data || res
    const isEmpty = data.is_empty === true
    const tableCount = typeof data.table_count === 'number' ? data.table_count : -1

    testResult.value = {
      success: data.success,
      message: data.message,
      response_time_ms: data.response_time_ms || 0,
      is_empty: isEmpty,
      table_count: tableCount
    }

    // 关键判断：
    // - success=true → 空库且连接正常 → 允许进入下一步
    // - success=false + tableCount>=0 + !isEmpty → 非空库 → 强制显示警告，阻止下一步
    // - 其他 success=false → 普通连接失败
    if (data.success) {
      dbConnectionOk.value = true
      databaseNotEmptyWarning.value = false
    } else if (tableCount >= 0 && !isEmpty) {
      // 连接成功但数据库非空：显示醒目警告，禁止下一步
      dbConnectionOk.value = false
      databaseNotEmptyWarning.value = true
      ElMessage({
        type: 'error',
        message: '当前数据库不为空，请更换为空数据库后再继续！',
        duration: 5000,
        showClose: true
      })
    } else {
      // 普通连接失败
      dbConnectionOk.value = false
      databaseNotEmptyWarning.value = false
    }
  } catch (e) {
    testResult.value = {
      success: false,
      message: e.message || '连接测试失败',
      response_time_ms: 0,
      is_empty: false,
      table_count: -1
    }
    dbConnectionOk.value = false
    databaseNotEmptyWarning.value = false
  } finally {
    testingConnection.value = false
  }
}

// 监听管理员表单验证
const validateAdminForm = async () => {
  if (!adminFormRef.value) {
    adminFormValid.value = false
    return
  }
  try {
    await adminFormRef.value.validate()
    adminFormValid.value = true
  } catch {
    adminFormValid.value = false
  }
}

// 监听管理员表单变化，实时更新验证状态
watch(
  () => [adminForm.username, adminForm.password, adminForm.confirmPassword, adminForm.email],
  () => {
    nextTick(() => {
      if (adminFormRef.value) {
        adminFormRef.value.validate((valid) => {
          adminFormValid.value = valid
        })
      }
    })
  }
)

// 执行安装
const handleExecuteInstall = async () => {
  if (!adminFormRef.value) return

  try {
    await adminFormRef.value.validate()
  } catch {
    ElMessage.error('请检查管理员表单填写')
    return
  }

  installing.value = true
  currentStep.value = 3
  installProgress.value = 10
  installLogs.value = [
    { type: 'info', message: '正在写入配置文件...' }
  ]

  // 模拟进度
  const steps = [
    { progress: 20, log: { type: 'info', message: '配置文件写入完成' } },
    { progress: 35, log: { type: 'info', message: '正在初始化数据库...' } },
    { progress: 50, log: { type: 'info', message: '正在创建数据表...' } },
    { progress: 65, log: { type: 'info', message: '数据表创建完成' } },
    { progress: 75, log: { type: 'info', message: '正在创建管理员账户...' } },
    { progress: 85, log: { type: 'info', message: '正在初始化默认数据...' } },
    { progress: 95, log: { type: 'info', message: '准备完成...' } }
  ]

  let stepIndex = 0
  const progressTimer = setInterval(() => {
    if (stepIndex < steps.length) {
      const step = steps[stepIndex]
      installProgress.value = step.progress
      installLogs.value.push(step.log)
      stepIndex++
    }
  }, 400)

  try {
    const res = await executeInstallation({
      database: {
        db_host: dbForm.db_host,
        db_port: dbForm.db_port,
        db_name: dbForm.db_name,
        db_user: dbForm.db_user,
        db_password: dbForm.db_password,
        charset: dbForm.charset,
        minsize: dbForm.minsize,
        maxsize: dbForm.maxsize,
        timeout: dbForm.timeout,
        command_timeout: dbForm.timeout,
        auto_create_db: dbForm.auto_create_db
      },
      admin: {
        username: adminForm.username,
        password: adminForm.password,
        email: adminForm.email || `${adminForm.username}@example.com`,
        alias: adminForm.alias
      },
      server: {
        app_port: serverForm.app_port,
        app_debug: serverForm.app_debug,
        frontend_name: serverForm.frontend_name,
        backend_name: serverForm.backend_name
      }
    })

    clearInterval(progressTimer)
    
    installProgress.value = 100
    installStatus.value = 'success'
    installLogs.value.push({ type: 'success', message: '系统安装成功！' })
    installLogs.value.push({ type: 'info', message: '请在手动重启应用服务后登录' })
    
    const data = res.data || res
    installResult.value = data
    
    // 保存安装状态到 localStorage
    localStorage.setItem('system_installed', 'true')
    localStorage.setItem('install_time', new Date().toISOString())

    // 直接跳转到安装完成页（步骤4），提示用户手动重启
    currentStep.value = 4
    installing.value = false

  } catch (e) {
    clearInterval(progressTimer)
    installStatus.value = 'error'
    installLogs.value.push({ 
      type: 'error', 
      message: `安装失败：${e.response?.data?.detail || e.message}` 
    })
    installing.value = false
    ElMessage.error(`安装失败：${e.response?.data?.detail || e.message}`)
  }
}

// 根据配置获取安装后跳转路径
const getInstallRedirectPath = () => {
  return systemStore.install_redirect === 'home' ? '/' : '/panel/login'
}

// 跳转到登录页（已重启确认后）
const goToLogin = async () => {
  // 先验证后端服务是否已恢复
  try {
    const res = await getInstallStatus()
    const data = res.data || res
    if (!data.installed) {
      // 后端已重启但仍未识别为已安装
      ElMessage.warning('服务尚未就绪，请确认已重启应用服务')
      return
    }
  } catch (e) {
    // 后端未启动 / 连接失败
    ElMessage.error('无法连接到后端服务，请确认已重启应用服务')
    return
  }

  // 确保安装状态已保存
  localStorage.setItem('system_installed', 'true')
  const redirectPath = getInstallRedirectPath()
  router.push({
    path: redirectPath,
    query: redirectPath === '/panel/login' ? { installed: '1' } : {}
  })
}

// 检查安装状态，返回是否已安装
const checkInstallStatus = async () => {
  try {
    const res = await getInstallStatus()
    const data = res.data || res
    if (data.installed) {
      const redirectPath = getInstallRedirectPath()
      ElMessage.info(redirectPath === '/' ? '系统已安装，正在跳转至首页' : '系统已安装，正在跳转至登录页')
      localStorage.setItem('system_installed', 'true')
      router.replace(redirectPath)
      return true
    }
  } catch (e) {
    // 未安装时可能会返回 404，忽略
    console.log('安装状态检查完成')
  }
  return false
}

onMounted(async () => {
  // 加载现有配置并填充表单
  try {
    await systemStore.loadConfig()
    // 用 config.conf 中的现有值填充表单（支持重新安装时回显）
    if (systemStore.frontend_name) {
      serverForm.frontend_name = systemStore.frontend_name
    }
    if (systemStore.backend_name) {
      serverForm.backend_name = systemStore.backend_name
    }
  } catch (_) {}

  // 检查安装状态：如果系统已安装则跳转到登录页
  const alreadyInstalled = await checkInstallStatus()
  if (alreadyInstalled) return

  await doEnvCheck()
})

// 执行环境检测
const doEnvCheck = async () => {
  envChecking.value = true
  try {
    const res = await envCheck()
    const data = res.data || res
    const items = []

    // 操作系统
    if (data.os) {
      items.push({
        name: '操作系统',
        value: data.os.display || data.os.name,
        status: data.os.status || 'success',
        desc: data.os.desc || '支持的操作系统'
      })
    }

    // Python版本
    if (data.python) {
      items.push({
        name: 'Python 版本',
        value: data.python.version,
        status: data.python.status || 'success',
        desc: data.python.desc || ''
      })
    }

    // 其他检测项
    if (data.checks && Array.isArray(data.checks)) {
      items.push(...data.checks)
    }

    envChecks.value = items
  } catch (e) {
    console.error('环境检测失败:', e)
    envChecks.value = [
      { name: '操作系统', value: '检测失败', status: 'error', desc: '无法获取操作系统信息' },
      { name: 'Python 版本', value: '检测失败', status: 'error', desc: '无法获取 Python 版本' },
      { name: '文件写入权限', value: '检测失败', status: 'error', desc: '请检查后端服务是否正常' }
    ]
  } finally {
    envChecking.value = false
  }
}

onUnmounted(() => {
  if (installTimer) {
    clearInterval(installTimer)
  }
})
</script>

<style scoped lang="scss">
.install-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.install-card {
  width: 100%;
  max-width: 720px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  padding: 40px;
}

.install-header {
  text-align: center;
  margin-bottom: 30px;
}

.install-title {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 10px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.title-icon {
  color: #667eea;
  font-size: 32px;
  animation: spin 4s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.install-desc {
  color: #909399;
  margin: 0;
}

.install-steps {
  margin-bottom: 30px;
}

.install-content {
  min-height: 400px;
}

.step-content {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.env-check-card {
  margin-bottom: 20px;
}

.env-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.env-actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}

.restart-status {
  margin-top: 16px;

  .restart-info {
    display: flex;
    align-items: center;
    gap: 8px;

    .el-icon.is-loading {
      animation: rotating 1.5s linear infinite;
    }
  }
}

@keyframes rotating {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.env-item {
  display: grid;
  grid-template-columns: 150px 150px 1fr;
  gap: 15px;
  padding: 10px 15px;
  background: #f5f7fa;
  border-radius: 8px;
  align-items: center;
}

.env-name {
  font-weight: 500;
  color: #303133;
}

.env-value {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
  
  &.success { color: #67c23a; }
  &.warning { color: #e6a23c; }
  &.error { color: #f56c6c; }
}

.env-desc {
  color: #909399;
  font-size: 13px;
}

.step-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid #ebeef5;
}

.db-form, .admin-form {
  max-width: 550px;
  margin: 0 auto;
}

.db-test-section {
  display: flex;
  align-items: center;
  gap: 15px;
  justify-content: center;
  margin: 20px 0;
  padding: 15px;
  background: #f5f7fa;
  border-radius: 8px;
}

.test-result {
  display: flex;
  align-items: center;
  gap: 5px;
  font-weight: 500;
  
  &.success { color: #67c23a; }
  &.error { color: #f56c6c; }
}

.response-time {
  font-size: 12px;
  color: #909399;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}

.checkbox-desc {
  color: #606266;
  font-size: 13px;
}

.auto-create-wrapper {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  width: 100%;
}

.auto-create-wrapper .el-checkbox {
  margin-right: 0;
}

.auto-create-wrapper span {
  white-space: normal;
  word-break: break-all;
}

.help-icon {
  color: #909399;
  margin-left: 6px;
  cursor: help;
  flex-shrink: 0;
}

.empty-db-alert {
  margin-bottom: 20px;
  border-radius: 10px;

  .alert-body {
    text-align: left;
    font-size: 14px;
    color: #606266;
    line-height: 1.7;

    p {
      margin: 6px 0;
    }

    strong {
      color: #f56c6c;
    }

    .alert-actions {
      color: #f56c6c;
      font-weight: 500;
      margin-top: 10px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .alert-suggestions {
      margin: 8px 0 0 0;
      padding-left: 20px;
      color: #606266;

      li {
        margin-bottom: 4px;
      }
    }
  }
}

.table-count-tag {
  display: inline-block;
  margin-left: 10px;
  padding: 1px 8px;
  background: #909399;
  color: #fff;
  border-radius: 10px;
  font-size: 12px;

  &:not(.success) + & {
    background: #f56c6c;
  }
}

.test-result.error .table-count-tag {
  background: #f56c6c;
}
.test-result.success .table-count-tag {
  background: #67c23a;
}

.install-progress {
  text-align: center;
  padding: 20px 0;
}

.install-logs {
  margin-top: 30px;
  text-align: left;
  max-height: 300px;
  overflow-y: auto;
}

.log-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin-bottom: 8px;
  border-radius: 6px;
  font-size: 14px;
  animation: slideIn 0.3s ease;
  
  &.info {
    background: #ecf5ff;
    color: #409eff;
  }
  &.success {
    background: #f0f9eb;
    color: #67c23a;
  }
  &.error {
    background: #fef0f0;
    color: #f56c6c;
  }
}

@keyframes slideIn {
  from { opacity: 0; transform: translateX(-10px); }
  to { opacity: 1; transform: translateX(0); }
}

.install-result-info {
  margin-bottom: 20px;
}

.warning-text {
  margin-top: 15px;
  padding: 12px;
  background: #fdf6ec;
  border: 1px solid #faecd8;
  border-radius: 8px;
  color: #e6a23c;
  display: flex;
  align-items: center;
  gap: 8px;
}

.restart-required-alert {
  margin: 20px 0;
  border-radius: 10px;

  .restart-alert-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
    font-size: 15px;
  }

  .restart-alert-body {
    font-size: 14px;
    line-height: 1.8;
    text-align: left;

    p {
      margin: 6px 0;
    }

    .restart-steps {
      margin-top: 10px;
      font-weight: 500;
    }

    ol {
      margin: 8px 0 0 0;
      padding-left: 22px;

      li {
        margin-bottom: 4px;
      }
    }

    kbd {
      display: inline-block;
      padding: 2px 8px;
      background: #fff;
      border: 1px solid #dcdfe6;
      border-radius: 4px;
      font-family: 'Consolas', 'Monaco', monospace;
      font-size: 12px;
      color: #606266;
      margin: 0 2px;
    }

    code {
      background: #f5f7fa;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 13px;
      color: #e6a23c;
    }
  }
}

.restart-confirm-checkbox {
  margin-top: 12px;
  display: flex;
  justify-content: center;
}
</style>
