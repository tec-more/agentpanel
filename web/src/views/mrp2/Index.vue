<template>
  <div class="mrp2-index">
    <router-view />
    <el-card shadow="never" class="welcome-card">
      <div class="welcome-content">
        <div class="welcome-header">
          <h2>MRPII制造资源计划</h2>
          <p>集成销售预测、主生产计划、物料需求计划、能力需求计划和计划执行监控</p>
        </div>
        
        <div class="feature-grid">
          <div class="feature-item" @click="navigateTo('/mrp2/forecast')">
            <div class="feature-icon" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
              <span class="icon-text">📊</span>
            </div>
            <div class="feature-info">
              <h3>销售预测</h3>
              <p>基于历史数据和市场趋势进行销售预测，支持月度、季度、年度预测</p>
            </div>
          </div>
          
          <div class="feature-item" @click="navigateTo('/mrp2/mps')">
            <div class="feature-icon" style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);">
              <span class="icon-text">📅</span>
            </div>
            <div class="feature-info">
              <h3>主生产计划</h3>
              <p>根据销售预测制定生产计划，确定生产数量和时间安排</p>
            </div>
          </div>
          
          <div class="feature-item" @click="navigateTo('/mrp2/mrp')">
            <div class="feature-icon" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
              <span class="icon-text">📦</span>
            </div>
            <div class="feature-info">
              <h3>物料需求计划</h3>
              <p>根据BOM和库存计算物料需求，生成采购和生产建议</p>
            </div>
          </div>
          
          <div class="feature-item" @click="navigateTo('/mrp2/crp')">
            <div class="feature-icon" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
              <span class="icon-text">⚙️</span>
            </div>
            <div class="feature-info">
              <h3>能力需求计划</h3>
              <p>分析工作中心能力负荷，确保生产计划的可行性</p>
            </div>
          </div>
          
          <div class="feature-item" @click="navigateTo('/mrp2/monitor')">
            <div class="feature-icon" style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);">
              <span class="icon-text">👁️</span>
            </div>
            <div class="feature-info">
              <h3>计划执行监控</h3>
              <p>实时监控计划执行进度，及时发现异常并预警</p>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <el-row :gutter="20">
      <el-col :span="8">
        <el-card shadow="never" class="summary-card">
          <template #header>
            <span>计划概览</span>
          </template>
          <div class="summary-content">
            <div class="summary-item">
              <div class="summary-value">{{ planStats.total }}</div>
              <div class="summary-label">总计划数</div>
            </div>
            <div class="summary-item">
              <div class="summary-value draft">{{ planStats.draft }}</div>
              <div class="summary-label">草稿</div>
            </div>
            <div class="summary-item">
              <div class="summary-value pending">{{ planStats.pending }}</div>
              <div class="summary-label">待审核</div>
            </div>
            <div class="summary-item">
              <div class="summary-value approved">{{ planStats.approved }}</div>
              <div class="summary-label">已发布</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="never" class="summary-card">
          <template #header>
            <span>异常预警</span>
          </template>
          <div v-if="alerts.length > 0" class="alert-list">
            <div v-for="alert in alerts" :key="alert.id" class="alert-item" :class="alert.level">
              <el-tag :type="alert.level === 'warning' ? 'warning' : 'danger'" size="small">{{ alert.level === 'warning' ? '警告' : '严重' }}</el-tag>
              <span class="alert-message">{{ alert.message }}</span>
              <span class="alert-time">{{ alert.time }}</span>
            </div>
          </div>
          <div v-else class="empty-alert">
            <span class="empty-icon">✅</span>
            <p>暂无异常预警</p>
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card shadow="never" class="summary-card">
          <template #header>
            <span>快速操作</span>
          </template>
          <div class="quick-actions">
            <el-button type="primary" block @click="navigateTo('/mrp2/forecast')">
              + 新增销售预测
            </el-button>
            <el-button type="success" block @click="navigateTo('/mrp2/mps')">
              + 新增主生产计划
            </el-button>
            <el-button type="warning" block @click="navigateTo('/mrp2/mrp')">
              + 计算物料需求
            </el-button>
            <el-button type="info" block @click="navigateTo('/mrp2/crp')">
              + 计算能力需求
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import request from '@/utils/request'
import { useRouter } from 'vue-router'

const router = useRouter()

const planStats = reactive({
  total: 0,
  draft: 0,
  pending: 0,
  approved: 0
})

const alerts = ref([])

const navigateTo = (path) => {
  router.push(`/panel${path}`)
}

const fetchStats = async () => {
  try {
    const forecastData = await request.get('/v1/mrp2/forecast/', { params: { page_size: 1 } })
    const mpsData = await request.get('/v1/mrp2/mps/', { params: { page_size: 1 } })
    const mrpData = await request.get('/v1/mrp2/mrp/', { params: { page_size: 1 } })
    const crpData = await request.get('/v1/mrp2/crp/', { params: { page_size: 1 } })
    
    planStats.total = forecastData.data?.total || 0 + mpsData.data?.total || 0 + mrpData.data?.total || 0 + crpData.data?.total || 0
    
    const draftData = await request.get('/v1/mrp2/forecast/', { params: { status: 'draft', page_size: 1 } })
    planStats.draft = draftData.data?.total || 0
    
    const pendingData = await request.get('/v1/mrp2/forecast/', { params: { status: 'pending', page_size: 1 } })
    planStats.pending = pendingData.data?.total || 0
    
    const approvedData = await request.get('/v1/mrp2/forecast/', { params: { status: 'approved', page_size: 1 } })
    planStats.approved = approvedData.data?.total || 0
  } catch (error) {
    console.error('获取统计数据失败', error)
  }
}

const fetchAlerts = async () => {
  alerts.value = [
    { id: 1, level: 'warning', message: '物料 A001 库存低于安全库存', time: '5分钟前' },
    { id: 2, level: 'danger', message: '工作中心 WC-001 负荷超过120%', time: '10分钟前' },
    { id: 3, level: 'warning', message: '订单 PO-001 预计延期交付', time: '30分钟前' }
  ]
}

onMounted(() => {
  fetchStats()
  fetchAlerts()
})
</script>

<style lang="scss" scoped>
.mrp2-index {
  padding: 20px;
  
  .welcome-card {
    margin-bottom: 20px;
    
    .welcome-content {
      .welcome-header {
        text-align: center;
        margin-bottom: 30px;
        
        h2 {
          font-size: 28px;
          font-weight: 600;
          color: #333;
          margin-bottom: 8px;
        }
        
        p {
          color: #666;
          font-size: 14px;
        }
      }
      
      .feature-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 20px;
        
        @media (max-width: 1200px) {
          grid-template-columns: repeat(2, 1fr);
        }
        
        @media (max-width: 768px) {
          grid-template-columns: 1fr;
        }
        
        .feature-item {
          display: flex;
          align-items: center;
          gap: 16px;
          padding: 20px;
          background: #fafafa;
          border-radius: 12px;
          cursor: pointer;
          transition: all 0.3s ease;
          
          &:hover {
            background: #f0f0f0;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
          }
          
          .feature-icon {
            width: 56px;
            height: 56px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            
            .icon-text {
              font-size: 24px;
            }
          }
          
          .feature-info {
            flex: 1;
            
            h3 {
              font-size: 16px;
              font-weight: 600;
              color: #333;
              margin-bottom: 4px;
            }
            
            p {
              font-size: 13px;
              color: #666;
              line-height: 1.5;
            }
          }
        }
      }
    }
  }
  
  .summary-card {
    .summary-content {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 16px;
      
      .summary-item {
        text-align: center;
        padding: 16px;
        background: #fafafa;
        border-radius: 8px;
        
        .summary-value {
          font-size: 28px;
          font-weight: 700;
          color: #333;
          
          &.draft { color: #909399; }
          &.pending { color: #e6a23c; }
          &.approved { color: #67c23a; }
        }
        
        .summary-label {
          font-size: 12px;
          color: #999;
          margin-top: 4px;
        }
      }
    }
    
    .alert-list {
      .alert-item {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px;
        margin-bottom: 8px;
        background: #fef0f0;
        border-radius: 6px;
        
        &.warning {
          background: #fdf6ec;
        }
        
        .alert-message {
          flex: 1;
          font-size: 13px;
          color: #666;
        }
        
        .alert-time {
          font-size: 12px;
          color: #999;
        }
      }
    }
    
    .empty-alert {
      text-align: center;
      padding: 30px;
      
      .empty-icon {
        font-size: 32px;
        display: block;
        margin-bottom: 8px;
      }
      
      p {
        color: #999;
        font-size: 14px;
      }
    }
    
    .quick-actions {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
  }
}
</style>
