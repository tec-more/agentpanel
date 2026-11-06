<template>
  <div class="flow-canvas-wrap">
    <!-- 左侧节点库 -->
    <div class="node-palette">
      <div class="palette-title">节点库</div>
      <div
        v-for="nt in nodeTypeList"
        :key="nt.key"
        class="palette-item"
        :style="{ '--c': nt.color }"
        @click="addNode(nt.key)"
      >
        <span class="dot"></span>
        <div>
          <div class="p-name">{{ nt.label }}</div>
          <div class="p-desc">{{ nt.desc }}</div>
        </div>
      </div>
      <el-divider />
      <div class="palette-tip">
        点击添加节点，拖拽连线即可配置审批走向。<br />
        选中节点 / 连线可在右侧配置。
      </div>
    </div>

    <!-- 中央画布 -->
    <div class="canvas-main">
      <div class="canvas-toolbar">
        <span class="ct-title">审批流程设计器</span>
        <div class="ct-actions">
          <el-button size="small" @click="fitView()">适应画布</el-button>
          <el-button size="small" type="danger" plain :disabled="!selected" @click="deleteSelected">
            删除选中
          </el-button>
        </div>
      </div>
      <div class="vue-flow-host">
        <VueFlow
          :nodes="nodes"
          :edges="edges"
          :delete-key-code="['Delete', 'Backspace']"
          :default-edge-options="{ type: 'smoothstep' }"
          @node-click="onNodeClick"
          @edge-click="onEdgeClick"
          @connect="onConnect"
          @pane-click="onPaneClick"
        >
          <template #node-approvalNode="nodeProps">
            <div
              class="flow-node"
              :class="['nt-' + nodeProps.data.nodeType, { selected: nodeProps.selected }]"
              :style="{ '--c': nodeColor(nodeProps.data.nodeType) }"
            >
              <Handle
                v-if="nodeProps.data.nodeType !== 'start'"
                type="target"
                :position="Position.Top"
              />
              <div class="fn-head">
                <span class="fn-icon">
                  <el-icon><component :is="nodeIcon(nodeProps.data.nodeType)" /></el-icon>
                </span>
                <span class="fn-name">{{ nodeProps.data.name || nodeTypeLabel(nodeProps.data.nodeType) }}</span>
              </div>
              <div class="fn-body" v-if="nodeProps.data.nodeType === 'approve'">
                <el-tag size="small" :type="modeTag(nodeProps.data.approve_type)" effect="dark">
                  {{ modeLabel(nodeProps.data.approve_type) }}
                </el-tag>
                <span class="fn-src">{{ approverSummary(nodeProps.data.approver_config) }}</span>
              </div>
              <div class="fn-body" v-else-if="nodeProps.data.nodeType === 'condition'">
                <span class="fn-cond">
                  {{ nodeProps.data.field || '字段' }}
                  {{ nodeProps.data.operator || '>' }}
                  {{ nodeProps.data.value ?? '' }}
                </span>
              </div>
              <Handle
                v-if="nodeProps.data.nodeType !== 'end'"
                type="source"
                :position="Position.Bottom"
              />
            </div>
          </template>

          <Background :gap="18" pattern-color="#dbe3ee" />
          <Controls />
          <MiniMap pannable zoomable />
        </VueFlow>
      </div>
    </div>

    <!-- 右侧配置面板 -->
    <div class="config-side" v-if="selectedTarget">
      <div class="side-head">
        <span>配置</span>
        <el-icon class="close" @click="selected = null"><Close /></el-icon>
      </div>
      <FlowNodePanel
        :target="selectedTarget"
        :kind="selected.kind"
        :source-node-type="selected.sourceNodeType"
        :source-name="selected.sourceName"
        :target-name="selected.targetName"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { VueFlow, useVueFlow, Handle, Position } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'
import {
  NODE_TYPES, NODE_TYPE_LIST, genNodeId, createNodeData
} from './flowNodeMeta'
import FlowNodePanel from './FlowNodePanel.vue'

const { nodes, edges, addNodes, addEdges, removeNodes, removeEdges,
        setNodes, setEdges, findNode, findEdge, fitView } = useVueFlow()

const nodeTypeList = NODE_TYPE_LIST
const selected = ref(null) // { kind:'node'|'edge', id, sourceNodeType?, sourceName?, targetName? }

const selectedTarget = computed(() => {
  if (!selected.value) return null
  return selected.value.kind === 'node' ? findNode(selected.value.id) : findEdge(selected.value.id)
})

// ---------- 工具 ----------
function nodeColor(t) { return NODE_TYPES[t]?.color || '#6B7280' }
function nodeIcon(t) { return NODE_TYPES[t]?.icon || 'CircleCheck' }
function nodeTypeLabel(t) { return NODE_TYPES[t]?.label || t }
function modeLabel(m) { return m === 'joint' ? '会签' : m === 'or' ? '或签' : '单人' }
function modeTag(m) { return m === 'joint' ? 'warning' : m === 'or' ? 'success' : 'info' }
function approverSummary(cfg) {
  if (!cfg) return ''
  if (cfg.type === 'user') return `指定用户 · ${(cfg.user_ids || []).length} 人`
  if (cfg.type === 'role') return `角色 · ${(cfg.role_ids || []).length} 个`
  if (cfg.type === 'dept_head') return cfg.use_applicant_dept === false ? '指定部门主管' : '申请人部门主管'
  if (cfg.type === 'dynamic') return '动态(申请人部门主管)'
  return ''
}

function genEdgeId() { return `e_${Date.now().toString(36)}_${Math.floor(Math.random() * 1e4).toString(36)}` }

// ---------- 布局（基于 BFS 层级） ----------
function layoutPositions(nodeList, edgeList) {
  const adj = {}
  nodeList.forEach(n => (adj[n.id] = []))
  edgeList.forEach(e => { if (adj[e.source]) adj[e.source].push(e.target) })
  const level = {}
  const queue = nodeList.filter(n => n.type === 'start').map(n => n.id)
  if (!queue.length && nodeList.length) queue.push(nodeList[0].id)
  queue.forEach(id => (level[id] = 0))
  while (queue.length) {
    const cur = queue.shift()
    for (const t of adj[cur] || []) {
      if (level[t] === undefined) { level[t] = level[cur] + 1; queue.push(t) }
    }
  }
  let maxLevel = 0
  Object.values(level).forEach(v => (maxLevel = Math.max(maxLevel, v)))
  nodeList.forEach(n => { if (level[n.id] === undefined) level[n.id] = maxLevel + 1 })
  const byLevel = {}
  nodeList.forEach(n => { (byLevel[level[n.id]] = byLevel[level[n.id]] || []).push(n.id) })
  const pos = {}
  Object.entries(byLevel).forEach(([lvl, ids]) => {
    ids.forEach((id, i) => { pos[id] = { x: 80 + Number(lvl) * 300, y: 80 + i * 150 } })
  })
  return pos
}

// ---------- 节点数据归一化 ----------
function normalizeNodeData(n) {
  const data = { nodeType: n.type, name: n.name || NODE_TYPES[n.type]?.label || n.type }
  if (n.type === 'approve') {
    data.approve_type = n.approve_type || 'single'
    data.approver_config = n.approver_config || { type: 'user', user_ids: [] }
  } else if (n.type === 'condition') {
    data.field = n.field || ''
    data.operator = n.operator || '>'
    data.value = n.value ?? ''
  }
  return data
}

// ---------- 边视觉装饰 ----------
function applyEdgeVisual(edge, srcType) {
  const d = edge.data || {}
  if (srcType === 'condition') {
    const cond = d.condition
    edge.label = d.isDefault ? '默认' : (cond ? `${cond.field || ''} ${cond.operator || ''} ${cond.value ?? ''}` : '条件')
    edge.animated = false
    edge.style = { stroke: '#F59E0B' }
  } else {
    const action = d.action || 'approve'
    edge.label = action === 'reject' ? '拒绝' : '通过'
    edge.animated = action === 'reject'
    edge.style = {
      stroke: action === 'reject' ? '#EF4444' : '#10B981',
      strokeDasharray: action === 'reject' ? '6 5' : undefined
    }
  }
  edge.markerEnd = { color: edge.style.stroke }
  return edge
}

function decorateEdge(edge, nodeTypeMap, engineEdge) {
  const srcType = nodeTypeMap[edge.source]
  const d = {}
  if (srcType === 'condition') {
    const cond = engineEdge?.condition
    d.isDefault = cond == null
    d.condition = cond || { field: '', operator: '>', value: '' }
  } else {
    d.action = engineEdge?.type === 'reject' ? 'reject' : 'approve'
  }
  edge.data = d
  return applyEdgeVisual(edge, srcType)
}

// ---------- 加载 / 序列化 ----------
function load(config) {
  let nodeList = []
  let edgeList = []
  if (config && Array.isArray(config.nodes) && config.nodes.length) {
    const pos = layoutPositions(config.nodes, config.edges || [])
    nodeList = config.nodes.map(n => ({
      id: n.id,
      type: 'approvalNode',
      position: pos[n.id] || { x: 120, y: 80 },
      data: normalizeNodeData(n)
    }))
    const nodeTypeMap = {}
    nodeList.forEach(n => (nodeTypeMap[n.id] = n.data.nodeType))
    edgeList = (config.edges || []).map(e => decorateEdge({
      id: genEdgeId(), source: e.source, target: e.target, type: 'smoothstep', data: {}
    }, nodeTypeMap, e))
  } else {
    nodeList = [
      { id: 'start', type: 'approvalNode', position: { x: 120, y: 80 }, data: createNodeData('start') },
      { id: 'end', type: 'approvalNode', position: { x: 120, y: 300 }, data: createNodeData('end') }
    ]
  }
  setNodes(nodeList)
  setEdges(edgeList)
  selected.value = null
  nextTick(() => fitView({ padding: 0.2 }))
}

function serialize() {
  const nodeTypeMap = {}
  const outNodes = nodes.value.map(n => {
    const d = n.data || {}
    nodeTypeMap[n.id] = d.nodeType
    const base = { id: n.id, type: d.nodeType, name: d.name }
    if (d.nodeType === 'approve') {
      base.approve_type = d.approve_type || 'single'
      base.approver_config = d.approver_config || { type: 'user', user_ids: [] }
    } else if (d.nodeType === 'condition') {
      base.field = d.field || ''
      base.operator = d.operator || '>'
      base.value = d.value ?? ''
    }
    return base
  })
  const outEdges = edges.value.map(e => {
    const d = e.data || {}
    const srcType = nodeTypeMap[e.source]
    const base = { source: e.source, target: e.target }
    if (srcType === 'condition') {
      base.condition = d.isDefault ? null : (d.condition || null)
    } else {
      base.type = d.action === 'reject' ? 'reject' : 'approve'
    }
    return base
  })
  return { nodes: outNodes, edges: outEdges }
}

// ---------- 交互 ----------
function addNode(type) {
  if (type === 'start') {
    const has = nodes.value.some(n => n.data?.nodeType === 'start')
    if (has) { import('element-plus').then(m => m.ElMessage.warning('只能有一个开始节点')); return }
  }
  const id = type === 'start' ? 'start' : type === 'end' ? 'end' : genNodeId(type)
  const position = { x: 180 + Math.random() * 160, y: 120 + Math.random() * 160 }
  addNodes([{ id, type: 'approvalNode', position, data: createNodeData(type) }])
}

function onNodeClick({ node }) {
  selected.value = { kind: 'node', id: node.id }
}
function onEdgeClick({ edge }) {
  const srcType = findNode(edge.source)?.data?.nodeType
  const srcName = findNode(edge.source)?.data?.name || edge.source
  const tgtName = findNode(edge.target)?.data?.name || edge.target
  selected.value = { kind: 'edge', id: edge.id, sourceNodeType: srcType, sourceName: srcName, targetName: tgtName }
}
function onConnect(connection) {
  const srcType = findNode(connection.source)?.data?.nodeType
  const data = srcType === 'condition'
    ? { isDefault: false, condition: { field: '', operator: '>', value: '' } }
    : { action: 'approve' }
  const nodeTypeMap = {}
  nodes.value.forEach(n => (nodeTypeMap[n.id] = n.data?.nodeType))
  const edge = decorateEdge({
    id: genEdgeId(), source: connection.source, target: connection.target, type: 'smoothstep', data: {}
  }, nodeTypeMap)
  addEdges([edge])
  const srcName = findNode(connection.source)?.data?.name || connection.source
  const tgtName = findNode(connection.target)?.data?.name || connection.target
  selected.value = { kind: 'edge', id: edge.id, sourceNodeType: srcType, sourceName: srcName, targetName: tgtName }
}
function onPaneClick() { selected.value = null }

function deleteSelected() {
  if (!selected.value) return
  if (selected.value.kind === 'node') {
    const n = findNode(selected.value.id)
    if (n) removeNodes([n])
  } else {
    const e = findEdge(selected.value.id)
    if (e) removeEdges([e])
  }
  selected.value = null
}

// 边数据变化后刷新视觉（连线标签/颜色）
watch(
  () => (selected.value?.kind === 'edge' ? JSON.stringify(findEdge(selected.value.id)?.data) : null),
  () => {
    const id = selected.value?.id
    if (!id) return
    const e = findEdge(id)
    if (e) applyEdgeVisual(e, findNode(e.source)?.data?.nodeType)
  }
)

defineExpose({ load, serialize })
</script>

<style scoped lang="scss">
.flow-canvas-wrap {
  display: flex;
  height: 560px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  background: #f5f7fa;
}
.node-palette {
  width: 180px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid #eef1f5;
  padding: 14px 12px;
  overflow-y: auto;
  .palette-title { font-weight: 600; font-size: 13px; color: #1f2937; margin-bottom: 10px; }
  .palette-item {
    display: flex; align-items: center; gap: 8px;
    padding: 8px; border-radius: 10px; cursor: pointer;
    border: 1px solid #eef1f5; margin-bottom: 8px; transition: all .2s;
    background: #fafbfc;
    &:hover { border-color: var(--c); box-shadow: 0 4px 12px rgba(37,99,235,.12); transform: translateY(-1px); }
    .dot { width: 10px; height: 10px; border-radius: 50%; background: var(--c); flex-shrink: 0; }
    .p-name { font-size: 13px; font-weight: 600; color: #1f2937; }
    .p-desc { font-size: 11px; color: #9ca3af; margin-top: 1px; }
  }
  .palette-tip { font-size: 11px; color: #9ca3af; line-height: 1.6; }
}
.canvas-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.canvas-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; background: #fff; border-bottom: 1px solid #eef1f5;
  .ct-title { font-weight: 600; font-size: 13px; color: #1f2937; }
}
.vue-flow-host { flex: 1; position: relative; }

.config-side {
  width: 320px; flex-shrink: 0; background: #fff;
  border-left: 1px solid #eef1f5; padding: 14px 16px; overflow-y: auto;
  .side-head {
    display: flex; align-items: center; justify-content: space-between;
    font-weight: 600; font-size: 14px; color: #1f2937; margin-bottom: 12px;
    .close { cursor: pointer; color: #9ca3af; &:hover { color: #ef4444; } }
  }
}

/* 节点卡片 */
.flow-node {
  min-width: 170px;
  background: rgba(255,255,255,.85);
  backdrop-filter: blur(6px);
  border: 1.5px solid var(--c);
  border-radius: 12px;
  padding: 10px 12px;
  box-shadow: 0 6px 18px rgba(15,23,42,.08);
  transition: all .2s ease;
  &:hover { transform: translateY(-2px); box-shadow: 0 10px 24px rgba(15,23,42,.14); }
  &.selected {
    border-width: 2.5px;
    box-shadow: 0 0 0 4px color-mix(in srgb, var(--c) 28%, transparent), 0 10px 24px rgba(15,23,42,.16);
  }
  .fn-head { display: flex; align-items: center; gap: 8px; }
  .fn-icon {
    width: 26px; height: 26px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    background: var(--c); color: #fff;
  }
  .fn-name { font-weight: 600; font-size: 13px; color: #1f2937; }
  .fn-body { margin-top: 8px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .fn-src { font-size: 11px; color: #6b7280; }
  .fn-cond { font-size: 12px; color: #b45309; background: #fef3c7; padding: 2px 8px; border-radius: 6px; }
}
</style>
