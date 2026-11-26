/** Dictionary namespace owned by the AgentPanel discovery entry. */
export const NS = 'agentpanelEntry'

export const zh = {
  'button.label': '发现应用',
  'button.aria': '发现应用',
  'panel.title': '发现应用',
  'panel.search': '搜索应用',
  'panel.frequent': '常用应用',
  'app.agentpanel': 'AgentPanel',
  'app.agentpanel.desc': '后台管理 · 业务支撑',
  'action.open': '打开客户门户',
  'state.opening': '正在打开…',
  'state.loading': '正在加载应用…',
  'state.empty': '暂无可用应用',
  'state.failed': '打开失败，请重试',
  'hint.signIn': '请先登录客户账号',
  'hint.notConfigured': '未配置 AgentPanel 门户地址',
  'login.title': '需要登录 AgentPanel',
  'login.desc': '请先登录 Harness 客户账号，登录后点击应用即可打开。',
  'login.action': '去登录',
  'login.cancel': '取消',
  'login.close': '关闭',
}
export const en = {
  'button.label': 'Discover apps',
  'button.aria': 'Discover apps',
  'panel.title': 'Discover apps',
  'panel.search': 'Search apps',
  'panel.frequent': 'Frequently used',
  'app.agentpanel': 'AgentPanel',
  'app.agentpanel.desc': 'Admin console and business support',
  'action.open': 'Open customer portal',
  'state.opening': 'Opening…',
  'state.loading': 'Loading apps…',
  'state.empty': 'No apps available',
  'state.failed': 'Failed to open. Please retry.',
  'hint.signIn': 'Sign in to your customer account first',
  'hint.notConfigured': 'AgentPanel portal URL is not configured',
  'login.title': 'Sign in to AgentPanel',
  'login.desc': 'Sign in with your Harness customer account first, then click the app to open it.',
  'login.action': 'Sign in',
  'login.cancel': 'Cancel',
  'login.close': 'Close',
}

/** Fallbacks keep the namespace key set identical across shipped locales. */
export const ja = { ...en }
export const es = { ...en }
export const fr = { ...en }
export const de = { ...en }
export const ru = { ...en }
export const pt = { ...en }
