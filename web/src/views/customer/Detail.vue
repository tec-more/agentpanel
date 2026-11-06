<template>
  <div class="customer-detail">
    <el-card shadow="never" class="detail-card">
      <template #header>
        <div class="card-header">
          <el-button type="primary" :icon="Back" @click="handleBack">返回列表</el-button>
          <span class="detail-title">客户详情</span>
        </div>
      </template>

      <div class="loading-container" v-if="loading">
        <el-skeleton :rows="10" animated />
      </div>

      <div v-else class="detail-content">
        <el-row :gutter="24">
          <el-col :span="24" class="detail-info">
            <h2 class="customer-name">{{ customer?.nickname || customer?.username }}</h2>
            <el-divider />

            <!-- 基本信息 -->
            <el-row :gutter="20">
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">客户ID:</span>
                  <span class="info-value">{{ customer?.id }}</span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">邮箱:</span>
                  <span class="info-value">{{ customer?.email || '-' }}</span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">手机:</span>
                  <span class="info-value">{{ customer?.phone || '-' }}</span>
                </div>
              </el-col>
            </el-row>

            <el-row :gutter="20">
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">用户名:</span>
                  <span class="info-value">{{ customer?.username || '-' }}</span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">昵称:</span>
                  <span class="info-value">{{ customer?.nickname || '-' }}</span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">状态:</span>
                  <el-tag v-if="customer?.is_active" type="success">
                    启用
                  </el-tag>
                  <el-tag v-else type="danger">
                    禁用
                  </el-tag>
                </div>
              </el-col>
            </el-row>

            <el-row :gutter="20">
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">注册时间:</span>
                  <span class="info-value">{{ customer?.created_at || '-' }}</span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">最后登录:</span>
                  <span class="info-value">{{ customer?.last_login || '-' }}</span>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="info-item">
                  <span class="info-label">登录次数:</span>
                  <span class="info-value">{{ customer?.login_count || 0 }} 次</span>
                </div>
              </el-col>
            </el-row>

            <el-divider />

            <!-- 会员信息 -->
            <div class="detail-section">
              <h3 class="section-title">
                <el-icon style="vertical-align: middle; margin-right: 8px;"><User /></el-icon>
                会员信息
              </h3>

              <el-card v-if="customer?.membership" shadow="never" class="membership-card">
                <el-row :gutter="20">
                  <el-col :span="6">
                    <div class="membership-item">
                      <div class="membership-label">会员等级</div>
                      <div class="membership-value">
                        <el-tag v-if="customer.level > 0" size="large" type="warning" effect="dark">
                          Lv{{ customer.level }}
                        </el-tag>
                        <el-tag v-else size="large" type="info" effect="plain">Lv0</el-tag>
                      </div>
                      <div class="membership-desc">基于总充值时长计算</div>
                    </div>
                  </el-col>
                  <el-col :span="6">
                    <div class="membership-item">
                      <div class="membership-label">会员状态</div>
                      <div class="membership-value">
                        <el-tag v-if="customer.membership.is_expired" size="large" type="danger" effect="plain">
                          已过期
                        </el-tag>
                        <el-tag v-else-if="customer.remaining_hours > 0" size="large" type="success">
                          有效期中
                        </el-tag>
                        <el-tag v-else size="large" type="warning" effect="plain">
                          已用完
                        </el-tag>
                      </div>
                      <div class="membership-desc">基于剩余时长判断</div>
                    </div>
                  </el-col>
                  <el-col :span="6">
                    <div class="membership-item">
                      <div class="membership-label">会员类型</div>
                      <div class="membership-value">
                        {{ customer.membership.level_name || '-' }}
                      </div>
                      <div class="membership-desc">会员等级配置</div>
                    </div>
                  </el-col>
                  <el-col :span="6">
                    <div class="membership-item">
                      <div class="membership-label">有效期</div>
                      <div class="membership-value">
                        <el-tag v-if="!customer.membership.is_expired" type="success">
                          有效
                        </el-tag>
                        <el-tag v-else type="danger">已过期</el-tag>
                      </div>
                      <div class="membership-desc">到期时间检查</div>
                    </div>
                  </el-col>
                </el-row>

                <el-divider />

                <el-row :gutter="20">
                  <el-col :span="8">
                    <div class="stat-item">
                      <div class="stat-icon" style="background: #ECF5FF;">
                        <el-icon color="#409EFF" :size="24"><Timer /></el-icon>
                      </div>
                      <div class="stat-content">
                        <div class="stat-label">充值总时长</div>
                        <div class="stat-value" style="color: #409EFF;">
                          {{ customer.membership.total_hours || 0 }}h
                        </div>
                        <div class="stat-desc">累计充值（决定等级）</div>
                      </div>
                    </div>
                  </el-col>
                  <el-col :span="8">
                    <div class="stat-item">
                      <div class="stat-icon" style="background: #F0F9FF;">
                        <el-icon color="#67C23A" :size="24"><Clock /></el-icon>
                      </div>
                      <div class="stat-content">
                        <div class="stat-label">剩余时长</div>
                        <div class="stat-value" style="color: #67C23A;">
                          {{ Number(customer.remaining_hours || 0).toFixed(1) }}h
                        </div>
                        <div class="stat-desc">可使用时长</div>
                      </div>
                    </div>
                  </el-col>
                  <el-col :span="8">
                    <div class="stat-item">
                      <div class="stat-icon" style="background: #FEF0F0;">
                        <el-icon color="#E6A23C" :size="24"><PieChart /></el-icon>
                      </div>
                      <div class="stat-content">
                        <div class="stat-label">已用时长</div>
                        <div class="stat-value" style="color: #E6A23C;">
                          {{ Number(customer.membership.used_hours || 0).toFixed(1) }}h
                        </div>
                        <div class="stat-desc">已消耗时长</div>
                      </div>
                    </div>
                  </el-col>
                </el-row>

                <el-divider />

                <el-row :gutter="20">
                  <el-col :span="12">
                    <div class="info-item">
                      <span class="info-label">开始时间:</span>
                      <span class="info-value">{{ formatDateTime(customer.membership.start_time) }}</span>
                    </div>
                  </el-col>
                  <el-col :span="12">
                    <div class="info-item">
                      <span class="info-label">到期时间:</span>
                      <span class="info-value" :style="{ color: customer.membership.is_expired ? '#F56C6C' : '#67C23A' }">
                        {{ formatDateTime(customer.membership.expire_time) }}
                      </span>
                    </div>
                  </el-col>
                </el-row>

                <div v-if="customer.membership.level_description" class="info-item">
                  <span class="info-label">等级描述:</span>
                  <span class="info-value">{{ customer.membership.level_description }}</span>
                </div>
              </el-card>

              <el-card v-else shadow="never" class="membership-card empty-membership">
                <el-empty description="该用户暂无会员信息">
                  <template #image>
                    <el-icon :size="60" color="#C0C4CC"><User /></el-icon>
                  </template>
                </el-empty>
              </el-card>
            </div>

            <el-divider />

            <!-- 操作按钮 -->
            <div class="detail-actions">
              <el-button type="primary" :icon="Edit" @click="handleEdit">编辑</el-button>
              <el-button v-if="customer?.is_active" type="warning" :icon="SwitchButton" @click="handleToggleStatus">禁用</el-button>
              <el-button v-else type="success" :icon="SwitchButton" @click="handleToggleStatus">启用</el-button>
              <el-button type="danger" :icon="Delete" @click="handleDelete">删除</el-button>
            </div>
          </el-col>
        </el-row>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Back,
  Edit,
  Delete,
  SwitchButton,
  User,
  Timer,
  Clock,
  PieChart
} from '@element-plus/icons-vue'
import { getCustomerDetail, toggleCustomerStatus, deleteCustomer } from '@/api/customer'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const customer = ref(null)

const customerId = computed(() => route.params.id)

// 格式化日期时间
const formatDateTime = (dateTime) => {
  if (!dateTime) return '-'
  const date = new Date(dateTime)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const fetchCustomerDetail = async () => {
  if (!customerId.value) return

  loading.value = true
  try {
    const res = await getCustomerDetail(customerId.value)
    customer.value = res.data
  } catch (e) {
    // 错误已处理
  } finally {
    loading.value = false
  }
}

const handleBack = () => {
  router.push('/panel/customer/list')
}

const handleEdit = () => {
  router.push(`/panel/customer/edit/${customerId.value}`)
}

const handleToggleStatus = async () => {
  try {
    await toggleCustomerStatus(customerId.value)
    ElMessage.success(customer.value.is_active ? '已禁用' : '已启用')
    fetchCustomerDetail()
  } catch (e) {
    // 错误已处理
  }
}

const handleDelete = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除客户 "${customer.value?.nickname || customer.value?.username}" 吗？`,
      '提示',
      {
        type: 'warning'
      }
    )
    await deleteCustomer(customerId.value)
    ElMessage.success('删除成功')
    router.push('/panel/customer/list')
  } catch (e) {
    // 取消或错误
  }
}

onMounted(() => {
  fetchCustomerDetail()
})
</script>

<style lang="scss" scoped>
.customer-detail {
  .detail-card {
    .card-header {
      display: flex;
      align-items: center;
      gap: 16px;

      .detail-title {
        font-size: 18px;
        font-weight: bold;
      }
    }
  }

  .loading-container {
    padding: 20px 0;
  }

  .detail-content {
    .detail-info {
      .customer-name {
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 20px;
      }

      .info-item {
        margin-bottom: 16px;
        display: flex;
        align-items: center;
        gap: 8px;

        .info-label {
          font-weight: bold;
          color: #606266;
          min-width: 80px;
        }

        .info-value {
          color: #303133;

          &.points {
            font-size: 18px;
            font-weight: bold;
            color: #e6a23c;
          }
        }

        .tag-item {
          margin-right: 8px;
        }

        .no-tags {
          color: #909399;
        }
      }
    }

    .detail-section {
      margin-top: 30px;

      .section-title {
        font-size: 16px;
        font-weight: bold;
        margin-bottom: 16px;
        color: #303133;
      }

      .description {
        color: #606266;
        line-height: 1.8;
      }
    }

    .membership-card {
      &.empty-membership {
        text-align: center;
        padding: 20px 0;
      }

      .membership-item {
        margin-bottom: 20px;

        .membership-label {
          font-size: 14px;
          color: #909399;
          margin-bottom: 8px;
        }

        .membership-value {
          font-size: 18px;
          font-weight: bold;
          color: #303133;
          margin-bottom: 4px;
        }

        .membership-desc {
          font-size: 12px;
          color: #C0C4CC;
        }
      }

      .stat-item {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 16px;
        background: #F5F7FA;
        border-radius: 8px;
        margin-bottom: 12px;

        .stat-icon {
          width: 56px;
          height: 56px;
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }

        .stat-content {
          flex: 1;

          .stat-label {
            font-size: 14px;
            color: #909399;
            margin-bottom: 4px;
          }

          .stat-value {
            font-size: 24px;
            font-weight: bold;
          }

          .stat-desc {
            font-size: 12px;
            color: #C0C4CC;
            margin-top: 2px;
          }
        }
      }
    }

    .detail-actions {
      margin-top: 40px;
      display: flex;
      gap: 12px;
    }
  }
}
</style>

