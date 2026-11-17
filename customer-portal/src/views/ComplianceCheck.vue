<template>
  <div>
    <el-card shadow="never">
      <template #header>
        <div class="card-head">
          <span>内容合规自检</span>
          <el-tag size="small" type="info">平台规则 + 本账号规则</el-tag>
        </div>
      </template>
      <el-form label-position="top">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="目标平台">
              <el-select v-model="form.platform" clearable placeholder="通用（不限平台）" style="width:100%">
                <el-option v-for="p in platforms" :key="p" :label="p" :value="p" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="检测通道">
              <el-select v-model="form.channel" style="width:100%">
                <el-option label="文本" value="text" />
                <el-option label="OCR 识别文本" value="ocr" />
                <el-option label="ASR 转录文本" value="asr" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="待检测内容">
          <el-input v-model="form.text" type="textarea" :rows="8"
            placeholder="粘贴待发布文案，系统将按合规规则实时检测…" maxlength="50000" show-word-limit />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="runCheck">开始检测</el-button>
        <el-button @click="reset">清空</el-button>
      </el-form>
    </el-card>

    <el-card v-if="result" shadow="never" class="result">
      <template #header>
        <div class="card-head">
          <span>检测结果</span>
          <div class="head-tags">
            <el-tag :type="verdictTag" effect="dark">{{ verdictText }}</el-tag>
            <el-tag size="small" type="info" v-if="result.pipeline_version">引擎 {{ result.pipeline_version }}</el-tag>
          </div>
        </div>
      </template>
      <el-descriptions :column="4" border size="small" class="summary">
        <el-descriptions-item label="命中数">{{ result.hit_count }}</el-descriptions-item>
        <el-descriptions-item label="P0 风险">{{ result.has_p0 ? '是' : '否' }}</el-descriptions-item>
        <el-descriptions-item label="P1 风险">{{ result.has_p1 ? '是' : '否' }}</el-descriptions-item>
        <el-descriptions-item label="需复核">{{ result.needs_review ? '是' : '否' }}</el-descriptions-item>
      </el-descriptions>
      <div class="meta-line">
        加载规则 {{ result.rules_loaded ?? '—' }} 条 · 全链路 {{ result.elapsed_ms ?? '—' }} ms
        <span v-if="result.normalized" class="normalized-flag">· 已做变体字符归一化（全角/零宽）</span>
      </div>

      <el-table v-if="result.hits?.length" :data="result.hits" style="width:100%;margin-top:12px" size="small">
        <el-table-column prop="level" label="等级" width="70">
          <template #default="{ row }"><el-tag :type="row.level === 'P0' ? 'danger' : 'warning'" size="small">{{ row.level }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="matched_text" label="命中内容" show-overflow-tooltip />
        <el-table-column prop="layer" label="层级" width="64">
          <template #default="{ row }"><el-tag size="small" effect="plain">{{ row.layer || '—' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="source" label="命中方法" width="100" show-overflow-tooltip>
          <template #default="{ row }"><span class="mono">{{ row.source || '—' }}</span></template>
        </el-table-column>
        <el-table-column prop="position" label="位置" width="70" />
        <el-table-column prop="action" label="处理" width="80" />
        <el-table-column prop="basis" label="依据" show-overflow-tooltip />
        <el-table-column prop="suggestion" label="建议" show-overflow-tooltip />
      </el-table>
      <el-empty v-else description="未检测到风险内容" :image-size="60" />
    </el-card>

    <!-- 检测过程：逐步轨迹（过程 / 步骤 / 方法 / 耗时 / 状态） -->
    <el-card v-if="result?.trace?.length" shadow="never" class="result">
      <template #header>
        <div class="card-head">
          <span>检测过程</span>
          <el-tag size="small">共 {{ result.trace.length }} 步 · 可展开查看每步方法</el-tag>
        </div>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="s in result.trace"
          :key="s.code"
          :timestamp="`步骤 ${s.step} · ${s.elapsed_ms} ms`"
          placement="top"
          :color="stepColor(s.status)"
          :hollow="s.status === 'skipped'"
        >
          <div class="step-head">
            <b>{{ s.name }}</b>
            <el-tag :type="stepTagType(s.status)" size="small" effect="light">{{ stepText(s.status) }}</el-tag>
            <span class="step-count" v-if="s.rules_scanned">扫描 {{ s.rules_scanned }} 条</span>
            <span class="step-count" v-if="s.hits_found">命中 {{ s.hits_found }} 处</span>
          </div>
          <div class="step-method"><span class="mono">{{ s.code }}</span> — {{ s.method }}</div>
          <div class="step-detail">{{ s.detail }}</div>
        </el-timeline-item>
      </el-timeline>
      <el-alert type="info" :closable="false" class="trace-note">
        说明：语义/LLM 层当前未接入模型，标注为"跳过"并给出原因；判定仅基于确定性规则，
        结论可复现、可追溯。所有步骤在服务端执行，前端仅展示轨迹。
      </el-alert>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { apiCheck } from '@/api'

const platforms = ['douyin', 'xiaohongshu', 'wechat', 'weibo', 'kuaishou', 'bilibili']
const form = ref({ text: '', platform: null, channel: 'text' })
const loading = ref(false)
const result = ref(null)

const verdictMap = {
  pass: { t: 'success', x: '通过' },
  pass_hint: { t: 'warning', x: '提示' },
  review: { t: 'warning', x: '需复核' },
  block: { t: 'danger', x: '拦截' }
}
const verdictTag = computed(() => verdictMap[result.value?.verdict]?.t || 'info')
const verdictText = computed(() => verdictMap[result.value?.verdict]?.x || result.value?.verdict)

const stepTagType = (s) => ({ applied: 'success', skipped: 'info', no_match: 'info' }[s] || 'info')
const stepText = (s) => ({ applied: '已执行', skipped: '跳过', no_match: '无匹配' }[s] || s)
const stepColor = (s) => ({ applied: '#67C23A', skipped: '#C0C4CC', no_match: '#E6A23C' }[s] || '#909399')

async function runCheck() {
  if (!form.value.text.trim()) { ElMessage.warning('请输入待检测内容'); return }
  loading.value = true
  try {
    const idem = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    const res = await apiCheck({
      text: form.value.text,
      platform: form.value.platform || undefined,
      channel: form.value.channel
    }, idem)
    result.value = res.data
  } catch (e) { /* 拦截器已提示 */ }
  finally { loading.value = false }
}

function reset() {
  form.value.text = ''
  result.value = null
}
</script>

<style scoped>
.card-head { display: flex; align-items: center; justify-content: space-between; }
.head-tags { display: flex; gap: 8px; align-items: center; }
.result { margin-top: 16px; }
.summary { margin-top: 4px; }
.meta-line { margin-top: 8px; font-size: 12px; color: #909399; }
.normalized-flag { color: #E6A23C; }
.mono { font-family: 'SFMono-Regular', Consolas, monospace; font-size: 12px; }
.step-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.step-count { font-size: 12px; color: #909399; }
.step-method { margin-top: 4px; font-size: 12px; color: #606266; }
.step-detail { margin-top: 2px; font-size: 12px; color: #909399; }
.trace-note { margin-top: 12px; }
</style>
