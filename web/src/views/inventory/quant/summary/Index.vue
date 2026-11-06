<template>
  <div class="quant-summary">
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon total">
              <el-icon :size="40"><Box /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ summary.total_sku || 0 }}</div>
              <div class="stat-label">SKU 总数</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon success">
              <el-icon :size="40"><Collection /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ summary.total_quantity || 0 }}</div>
              <div class="stat-label">库存总数量</div>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon warning">
              <el-icon :size="40"><Lock /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ summary.total_reserved || 0 }}</div>
              <div class="stat-label">预留数量</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="table-card" style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>按库位汇总</span>
        </div>
      </template>
      <el-table v-loading="loading" :data="locationSummary" border stripe>
        <el-table-column prop="location_name" label="库位" min-width="150" />
        <el-table-column prop="sku_count" label="SKU数量" width="120" align="center" />
        <el-table-column prop="total_quantity" label="总数量" width="120" align="center" />
        <el-table-column prop="total_reserved" label="预留数量" width="120" align="center" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Box, Collection, Lock } from '@element-plus/icons-vue'
import { getQuantSummary } from '@/api/inventory'

const loading = ref(false)
const summary = reactive({
  total_sku: 0,
  total_quantity: 0,
  total_reserved: 0
})
const locationSummary = ref([])

const fetchData = async () => {
  loading.value = true
  try {
    const res = await getQuantSummary()
    Object.assign(summary, res.data)
    locationSummary.value = res.data.by_location || []
  } catch (e) {
    console.error('获取库存汇总失败:', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchData()
})
</script>

<style lang="scss" scoped>
.quant-summary {
  .stat-card {
    .stat-content {
      display: flex;
      align-items: center;
      gap: 20px;
      .stat-icon {
        width: 70px;
        height: 70px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        &.total {
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        &.success {
          background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        &.warning {
          background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }
      }
      .stat-info {
        .stat-value {
          font-size: 28px;
          font-weight: bold;
          color: #303133;
        }
        .stat-label {
          font-size: 14px;
          color: #909399;
          margin-top: 4px;
        }
      }
    }
  }
  .table-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
  }
}
</style>


