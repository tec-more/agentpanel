<template>
  <div class="crm-stats">
    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span>商机漏斗</span></template>
          <div v-loading="loading.funnel">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="商机总数">{{ funnel.total_opportunities || 0 }}</el-descriptions-item>
              <el-descriptions-item label="预期总金额">¥{{ formatAmount(funnel.total_amount) }}</el-descriptions-item>
            </el-descriptions>
            <div v-for="stage in funnel.stages" :key="stage.stage_code" class="funnel-stage">
              <div class="stage-header">
                <span>{{ stage.stage_name }}</span>
                <span>{{ stage.opportunity_count }} 个 · ¥{{ formatAmount(stage.total_expected_amount) }}</span>
              </div>
              <el-progress :percentage="stage.conversion_rate" :stroke-width="16" />
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span>线索来源统计</span></template>
          <el-table v-loading="loading.sources" :data="leadSources.sources || []" border stripe size="small">
            <el-table-column prop="source_name" label="来源" />
            <el-table-column prop="lead_count" label="线索数" width="90" align="center" />
            <el-table-column prop="converted_count" label="转化数" width="90" align="center" />
            <el-table-column label="转化率" width="120">
              <template #default="{ row }">
                <el-progress :percentage="row.conversion_rate" :stroke-width="10" />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span>销售业绩</span></template>
          <el-table v-loading="loading.performance" :data="salesPerformance.performances || []" border stripe size="small">
            <el-table-column prop="user_name" label="销售" width="120" />
            <el-table-column prop="opportunity_count" label="商机数" width="80" align="center" />
            <el-table-column label="赢单金额" width="130" align="right">
              <template #default="{ row }">¥{{ formatAmount(row.won_amount) }}</template>
            </el-table-column>
            <el-table-column prop="avg_close_days" label="平均成交天数" width="120" align="center" />
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="never">
          <template #header><span>客户跟进情况</span></template>
          <el-table v-loading="loading.followup" :data="followUps.follow_ups || []" border stripe size="small">
            <el-table-column prop="customer_name" label="客户" min-width="120" />
            <el-table-column prop="activity_count" label="活动数" width="80" align="center" />
            <el-table-column prop="active_opportunity_count" label="活跃商机" width="90" align="center" />
            <el-table-column prop="last_follow_up_time" label="最后跟进" width="160" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getFunnelStats, getLeadSourceStats, getSalesPerformance, getCustomerFollowUp } from '@/api/crm'

const loading = reactive({ funnel: false, sources: false, performance: false, followup: false })
const funnel = ref({ stages: [], total_opportunities: 0, total_amount: 0 })
const leadSources = ref({ sources: [] })
const salesPerformance = ref({ performances: [] })
const followUps = ref({ follow_ups: [] })

const formatAmount = (v) => v ? Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2 }) : '0.00'

const fetchFunnel = async () => {
  loading.funnel = true
  try { funnel.value = await getFunnelStats().then(r => r.data) || { stages: [], total_opportunities: 0, total_amount: 0 } }
  catch (e) { console.error('获取漏斗统计失败:', e) }
  finally { loading.funnel = false }
}

const fetchSources = async () => {
  loading.sources = true
  try { leadSources.value = await getLeadSourceStats().then(r => r.data) || { sources: [] } }
  catch (e) { console.error('获取来源统计失败:', e) }
  finally { loading.sources = false }
}

const fetchPerformance = async () => {
  loading.performance = true
  try { salesPerformance.value = await getSalesPerformance().then(r => r.data) || { performances: [] } }
  catch (e) { console.error('获取业绩统计失败:', e) }
  finally { loading.performance = false }
}

const fetchFollowUps = async () => {
  loading.followup = true
  try { followUps.value = await getCustomerFollowUp().then(r => r.data) || { follow_ups: [] } }
  catch (e) { console.error('获取跟进统计失败:', e) }
  finally { loading.followup = false }
}

onMounted(() => { fetchFunnel(); fetchSources(); fetchPerformance(); fetchFollowUps() })
</script>

<style lang="scss" scoped>
.crm-stats {
  .funnel-stage { margin-top: 12px;
    .stage-header { display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 13px; }
  }
}
</style>
