/**
 * agentpanel 部署品牌：为桌面 Host 解析项目名。
 *
 * 项目名的唯一来源是后端配置文件 `config.conf` 的 `[app] name`（如
 * `AgentPanel`），由控制面以 `GET /v1/common/system-config` 公开。桌面主进程
 * 在启动 Host 前读取一次，通过 `DSH_AGENTPANEL_PROJECT_NAME` 注入 Host，供
 * `llm-deepseek-account` 的 `providerName` 使用——Web 界面的「模型」页和模型
 * 选择器随后用它替代默认的「DeepSeek 账号」标签。
 *
 * 任何失败（后端未启动、响应异常、名称为空）都静默回退：不设置环境变量，
 * Host 保持内置名称，界面维持原有「DeepSeek 账号 / DeepSeek Account」。
 */

/** 默认控制面客户体系基址，与 agentpanel-account-backend 保持一致。 */
const DEFAULT_CUSTOMER_URL = 'http://127.0.0.1:9998/v1/customer'

/** 名称长度上限，防止异常响应把超长文本写进环境变量和界面标签。 */
const MAX_PROJECT_NAME_LENGTH = 64

/**
 * 解析部署项目名。
 *
 * 优先级：显式设置的 `DSH_AGENTPANEL_PROJECT_NAME` 环境变量 > 控制面
 * `system-config` 的 `app_name`。两次读取都失败时返回 `undefined`。
 * @param timeoutMs - 控制面请求超时；默认 2 秒。
 * @returns 去除首尾空白后的项目名；不可用时为 `undefined`。
 */
export async function resolveAgentPanelProjectName(timeoutMs = 2_000): Promise<string | undefined> {
  const explicit = process.env.DSH_AGENTPANEL_PROJECT_NAME?.trim()
  if (explicit !== undefined && explicit !== '') return explicit
  const customerUrl = process.env.AGENTPANEL_CUSTOMER_URL || DEFAULT_CUSTOMER_URL
  let origin: URL
  try { origin = new URL(customerUrl) } catch { return undefined }
  try {
    const response = await fetch(new URL('/v1/common/system-config', origin).href, {
      signal: AbortSignal.timeout(timeoutMs),
    })
    if (!response.ok) return undefined
    const body = await response.json().catch(() => null) as { success?: boolean; data?: { app_name?: unknown } } | null
    if (body === null || body.success === false) return undefined
    const name = body.data?.app_name
    if (typeof name !== 'string') return undefined
    const trimmed = name.trim()
    return trimmed === '' || trimmed.length > MAX_PROJECT_NAME_LENGTH ? undefined : trimmed
  } catch {
    return undefined
  }
}
