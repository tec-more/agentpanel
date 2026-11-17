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
          <el-tag :type="verdictTag" effect="dark">{{ verdictText }}</el-tag>
        </div>
      </template>
      <el-descriptions :column="4" border size="small" class="summary">
        <el-descriptions-item label="命中数">{{ result.hit_count }}</el-descriptions-item>
        <el-descriptions-item label="P0 风险">{{ result.has_p0 ? '是' : '否' }}</el-descriptions-item>
        <el-descriptions-item label="P1 风险">{{ result.has_p1 ? '是' : '否' }}</el-descriptions-item>
        <el-descriptions-item label="需复核">{{ result.needs_review ? '是' : '否' }}</el-descriptions-item>
      </el-descriptions>
      <el-table v-if="result.hits?.length" :data="result.hits" style="width:100%;margin-top:16px" size="small">
        <el-table-column prop="level" label="等级" width="80">
          <template #default="{ row }"><el-tag :type="row.level === 'P0' ? 'danger' : 'warning'" size="small">{{ row.level }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="matched_text" label="命中内容" />
        <el-table-column prop="action" label="处理" width="90" />
        <el-table-column prop="basis" label="依据" />
        <el-table-column prop="suggestion" label="建议" />
      </el-table>
      <el-empty v-else description="未检测到风险内容" :image-size="60" />
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
.result { margin-top: 16px; }
.summary { margin-top: 4px; }
</style>
