#!/usr/bin/env node
/**
 * 一键验证 dsh Web UI 里的「发现应用（AgentPanel）」入口是否真的能用。
 *
 * 做的事：
 *   1. 探测 3080 是否已在跑；没跑就自己拉起来（--no-start 可禁用），并从日志里取一次性 token
 *   2. 用真实 Chrome（无头）打开页面，走 token → cookie 流程
 *   3. 断言四件事：页面渲染 / 插件客户端脚本被加载 / 「发现应用」按钮可见 / 点开后下拉面板正常
 *   4. 截图存到 dshw/.verify/，打印结果，按结果返回退出码（0 通过 / 1 失败）
 *
 * 用法（在 dshw 目录下）：
 *   node scripts/verify-agentpanel-entry.mjs            # 自动起服务 + 验证 + 关服务
 *   node scripts/verify-agentpanel-entry.mjs --keep      # 验证完保留服务，方便自己点
 *   node scripts/verify-agentpanel-entry.mjs --headed    # 显示浏览器窗口
 *   node scripts/verify-agentpanel-entry.mjs --token xxx # 复用已有服务的 token（不再启动）
 *   node scripts/verify-agentpanel-entry.mjs --signed-in # 已登录态：点卡片应直接跳转（需凭证有效）
 *   node scripts/verify-agentpanel-entry.mjs --url http://127.0.0.1:3080 --no-start
 *
 * 说明：服务已存在但没给 token 时无法通过 401 栅栏，脚本会提示用 --token 或先关掉它。
 */

import { spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import { existsSync, mkdirSync, readdirSync, writeFileSync, appendFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import http from 'node:http'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const DSHW = path.resolve(HERE, '..')
const OUT_DIR = path.join(DSHW, '.verify')
const SERVER_LOG = path.join(OUT_DIR, 'server.log')

// ───────────────────────── 参数 ─────────────────────────

function parseArgs(argv) {
  const a = {
    url: 'http://127.0.0.1:3080',
    token: null,
    start: true,
    keep: false,
    headed: false,
    json: false,
    signedIn: false,
    timeout: 60000,
    panelUrl: process.env.DSH_AGENTPANEL_PANEL_URL || 'http://127.0.0.1:9080',
    customerUrl: process.env.DSH_AGENTPANEL_CUSTOMER_URL || 'http://127.0.0.1:9080/v1/customer',
    // 发现应用目录 2026-11-26 迁入 harness；单独覆盖，customerUrl 仍承担登录/票据。
    appsEndpoint: process.env.DSH_AGENTPANEL_APPS_ENDPOINT || 'http://127.0.0.1:9080/v1/harness/discover-apps',
    gatewayUrl: process.env.DSH_AGENTPANEL_GATEWAY_URL || 'http://127.0.0.1:9999',
  }
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i]
    if (k === '--no-start') a.start = false
    else if (k === '--keep') a.keep = true
    else if (k === '--headed') a.headed = true
    else if (k === '--json') a.json = true
    else if (k === '--signed-in') a.signedIn = true
    else if (k === '--url') a.url = argv[++i]
    else if (k === '--token') a.token = argv[++i]
    else if (k === '--timeout') a.timeout = Number(argv[++i]) || a.timeout
    else if (k === '--panel-url') a.panelUrl = argv[++i]
    else if (k === '--customer-url') a.customerUrl = argv[++i]
    else if (k === '--gateway-url') a.gatewayUrl = argv[++i]
    else if (k === '-h' || k === '--help') {
      console.log('用法: node scripts/verify-agentpanel-entry.mjs [--keep] [--headed] [--no-start] [--signed-in] [--token <t>] [--url <u>] [--json]')
      process.exit(0)
    }
  }
  a.url = a.url.replace(/\/+$/, '')
  return a
}

// ───────────────────────── 小工具 ─────────────────────────

const C = {
  ok: (s) => `\x1b[32m${s}\x1b[0m`,
  bad: (s) => `\x1b[31m${s}\x1b[0m`,
  dim: (s) => `\x1b[90m${s}\x1b[0m`,
  bold: (s) => `\x1b[1m${s}\x1b[0m`,
}

function probe(url, timeoutMs = 3000) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: timeoutMs }, (res) => {
      res.resume()
      resolve({ up: true, status: res.statusCode })
    })
    req.on('error', () => resolve({ up: false, status: 0 }))
    req.on('timeout', () => { req.destroy(); resolve({ up: false, status: 0 }) })
  })
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

function resolvePlaywright() {
  const pnpmDir = path.join(DSHW, 'node_modules', '.pnpm')
  if (existsSync(pnpmDir)) {
    const dirs = readdirSync(pnpmDir)
      .filter((d) => d.startsWith('playwright-core@'))
      // 稳定版优先（避免 alpha 版本行为差异）
      .sort((x, y) => Number(x.includes('alpha')) - Number(y.includes('alpha')))
    for (const d of dirs) {
      const p = path.join(pnpmDir, d, 'node_modules', 'playwright-core')
      if (existsSync(path.join(p, 'package.json'))) return p
    }
  }
  try {
    const req = createRequire(path.join(DSHW, 'package.json'))
    return path.dirname(req.resolve('playwright-core/package.json'))
  } catch {
    return null
  }
}

function resolveChrome() {
  const cands = [
    process.env.CHROME_PATH,
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome',
    '/usr/bin/chromium',
  ].filter(Boolean)
  return cands.find((p) => existsSync(p)) || null
}

function killTree(pid) {
  if (!pid) return
  if (process.platform === 'win32') {
    spawn('taskkill', ['/pid', String(pid), '/T', '/F'], { stdio: 'ignore' })
  } else {
    try { process.kill(-pid, 'SIGTERM') } catch { try { process.kill(pid, 'SIGTERM') } catch {} }
  }
}

// ───────────────────────── 启动服务 ─────────────────────────

async function startServer(args) {
  mkdirSync(OUT_DIR, { recursive: true })
  writeFileSync(SERVER_LOG, '', 'utf8')

  const child = spawn(
    process.execPath,
    ['--import', 'tsx/esm', 'apps/cli/src/bin.ts', 'web', '--no-open'],
    {
      cwd: DSHW,
      env: {
        ...process.env,
        DSH_AGENTPANEL_CUSTOMER_URL: args.customerUrl,
        DSH_AGENTPANEL_APPS_ENDPOINT: args.appsEndpoint,
        DSH_AGENTPANEL_PANEL_URL: args.panelUrl,
        DSH_AGENTPANEL_GATEWAY_URL: args.gatewayUrl,
      },
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: process.platform !== 'win32',
    },
  )

  let token = null
  const onChunk = (buf) => {
    const s = buf.toString()
    appendFileSync(SERVER_LOG, s)
    if (!token) {
      const m = s.match(/[?&]token=([A-Za-z0-9_-]+)/)
      if (m) token = m[1]
    }
  }
  child.stdout.on('data', onChunk)
  child.stderr.on('data', onChunk)

  // 等端口起来 + 拿到 token
  const deadline = Date.now() + args.timeout
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      throw new Error(`服务启动即退出（code=${child.exitCode}），日志见 ${SERVER_LOG}`)
    }
    const p = await probe(`${args.url}/`)
    if (p.up && token) return { child, token }
    await sleep(500)
  }
  killTree(child.pid)
  throw new Error(`等待服务超时（${args.timeout}ms）。日志见 ${SERVER_LOG}`)
}

// ───────────────────────── 浏览器验证 ─────────────────────────

async function verifyInBrowser(args, token, childPid) {
  const pwPath = resolvePlaywright()
  if (!pwPath) throw new Error('找不到 playwright-core，先在 dshw 目录装依赖')
  const chrome = resolveChrome()
  if (!chrome) throw new Error('找不到 Chrome/Edge，可用环境变量 CHROME_PATH 指定')

  const { chromium } = createRequire(path.join(pwPath, 'package.json'))('playwright-core')
  const browser = await chromium.launch({
    executablePath: chrome,
    headless: !args.headed,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  })

  const checks = []
  const add = (name, pass, detail = '') => checks.push({ name, pass, detail })

  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const page = await ctx.newPage()

  const consoleErrors = []
  const pageErrors = []
  const pluginBundles = []

  page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 300)) })
  page.on('pageerror', (e) => pageErrors.push(String(e).slice(0, 300)))
  page.on('response', (res) => {
    const u = res.url()
    if (u.includes('agentpanel-entry')) pluginBundles.push({ url: u, status: res.status() })
  })

  const target = `${args.url}/?token=${encodeURIComponent(token)}`
  let navOk = false
  try {
    const res = await page.goto(target, { waitUntil: 'domcontentloaded', timeout: 30000 })
    navOk = !!res && res.status() < 400
  } catch (e) {
    add('打开页面', false, String(e).slice(0, 200))
  }

  if (navOk) {
    // 页面渲染（等 React 挂载）
    let bodyText = ''
    try {
      await page.waitForFunction(() => document.body && document.body.innerText.trim().length > 10, { timeout: 20000 })
      bodyText = await page.locator('body').innerText()
    } catch {}
    add('页面渲染', bodyText.trim().length > 10, `body 文本 ${bodyText.trim().length} 字`)

    // 入口按钮
    const btn = page.getByRole('button', { name: /发现应用|Discover/ })
    let visible = false
    try {
      await btn.first().waitFor({ state: 'visible', timeout: 20000 })
      visible = true
    } catch {}
    add('「发现应用」按钮可见', visible, visible ? '' : '侧栏未找到按钮（插件未装配或未激活？）')

    // 点开面板
    let panelText = ''
    if (visible) {
      await btn.first().click()
      await sleep(2500)
      panelText = await page.locator('body').innerText()
      const hasPanel = panelText.includes('常用应用')
      add('下拉面板展开', hasPanel, hasPanel ? '' : '点击后未出现「常用应用」分区')
      if (hasPanel) {
        // 未登录时也显示应用图标卡片（AP/AgentPanel），不再有红色登录提示。
        const hasCard = panelText.includes('AgentPanel')
        add('面板内容', hasCard, hasCard ? '应用卡片可见（图标 + 名称）' : '未找到应用卡片')
        const noRedHint = !panelText.includes('请先登录客户账号')
        add('无红色登录提示', noRedHint, noRedHint ? '' : '仍显示红色「请先登录客户账号」')

        // 点击后面板会关闭，先在展开态留一张截图（两种登录态都要留）。
        if (hasCard) {
          const panelShot = path.join(OUT_DIR, `panel-${new Date().toISOString().replace(/[:.]/g, '-')}.png`)
          await page.screenshot({ path: panelShot, fullPage: false })
        }

        // 已登录态：点卡片应签发 ticket 并打开新标签页（带 ticket/redirect），绝不弹登录框。
        // 覆盖回归：凭证文件在页面打开后才写入、或同一会话里刚登录，前端必须实时查询登录态。
        if (hasCard && args.signedIn) {
          const before = ctx.pages().length
          let popupUrl = ''
          let dialogOpened = false
          try {
            ctx.on('page', (p) => {
              p.on('framenavigated', (f) => { if (f === p.mainFrame() && popupUrl === '') popupUrl = p.url() })
            })
            await page.getByRole('button', { name: /AgentPanel/ }).first().click()
            await sleep(3000)
            dialogOpened = await page.getByRole('dialog').count() > 0
              && await page.getByRole('dialog').first().isVisible().catch(() => false)
          } catch {}
          add('已登录不弹登录框', !dialogOpened, dialogOpened ? '已登录仍提示去登录' : '未弹出登录提示框')
          const opened = ctx.pages().length > before
          add('已登录打开应用新页面', opened, opened ? `页面数 ${before} → ${ctx.pages().length}` : '点卡片未打开新页面')
          const hasTicket = /[?&]ticket=/.test(popupUrl)
          add('跳转携带 ticket', hasTicket, hasTicket ? popupUrl.slice(0, 120) : `URL: ${popupUrl || '(空)'}`)
          for (const p of ctx.pages()) if (p !== page) await p.close().catch(() => {})
        }

        // 未登录点击卡片 → 简单提示框 → 点「去登录」→ Harness 自带登录注册框。
        if (hasCard && !args.signedIn) {
          const pageCountBefore = ctx.pages().length
          let dialogVisible = false
          try {
            await page.getByRole('button', { name: /AgentPanel/ }).first().click()
            await page.getByRole('dialog').first().waitFor({ state: 'visible', timeout: 6000 })
            dialogVisible = true
          } catch {}
          add('未登录弹出登录提示', dialogVisible,
            dialogVisible ? '点击卡片后弹出登录提示框' : '未弹出登录提示框')
          // 锁死用户报告的 bug：ticket 拿不到时不能再显示「打开失败，请重试」红字，
          // 必须回退到登录提示框。lease 残留导致 signedIn=true 时也会走这条路径。
          const afterClickText = await page.locator('body').innerText()
          const noRedError = !afterClickText.includes('打开失败') && !afterClickText.includes('请重试')
          add('无「打开失败」红字', noRedError,
            noRedError ? '' : '点击卡片后仍显示红色「打开失败，请重试」')
          if (dialogVisible) {
            const dialog = page.getByRole('dialog').first()
            const dialogText = await dialog.innerText()
            const hasLoginCopy = /登录|Sign in/i.test(dialogText)
            add('登录提示文案正确', hasLoginCopy, hasLoginCopy ? '' : `弹框文案：${dialogText.slice(0, 80)}`)
            const hintShot = path.join(OUT_DIR, `login-hint-${new Date().toISOString().replace(/[:.]/g, '-')}.png`)
            await page.screenshot({ path: hintShot, fullPage: false })

            // 提示框里没有登录表单（那是第二步 Harness 的登录框负责的）。
            const inlineForm = await dialog.locator('input').count()
            add('提示框无内嵌登录表单', inlineForm === 0,
              inlineForm === 0 ? '' : `提示框内出现 ${inlineForm} 个输入框`)

            // 点「去登录」→ settings-account 的登录框应挂载（邮箱 + 密码）。
            let harnessForm = false
            try {
              await dialog.getByRole('button', { name: /去登录|Sign in/i }).first().click()
              await page.locator('input[type="email"]').first().waitFor({ state: 'visible', timeout: 6000 })
              await page.locator('input[type="password"]').first().waitFor({ state: 'visible', timeout: 6000 })
              harnessForm = true
            } catch {}
            add('去登录进入 Harness 登录注册框', harnessForm,
              harnessForm ? 'Harness 邮箱/密码登录表单已出现' : '未找到 Harness 登录注册表单')
            await sleep(400)
            const noJump = ctx.pages().length === pageCountBefore
            add('未登录不跳转应用', noJump, noJump ? '' : '未登录时打开了应用新页面')
            const dialogShot = path.join(OUT_DIR, `login-dialog-${new Date().toISOString().replace(/[:.]/g, '-')}.png`)
            await page.screenshot({ path: dialogShot, fullPage: false })
          }
        }
      }
    }

    // 插件脚本是否真的被浏览器加载
    const served = pluginBundles.filter((b) => b.status === 200)
    add(
      '插件客户端脚本已加载',
      served.length > 0,
      served.length ? `${served.length} 个请求 200` : '未观察到 agentpanel-entry 脚本请求',
    )

    // 运行时错误（过滤掉无登录态的噪音）
    const fatal = [...pageErrors, ...consoleErrors].filter(
      (e) => !/Failed to load resource|401|Unauthorized|net::ERR/i.test(e),
    )
    add('无运行时错误', fatal.length === 0, fatal.length ? fatal.slice(0, 2).join(' | ') : '')
  }

  mkdirSync(OUT_DIR, { recursive: true })
  const shot = path.join(OUT_DIR, `entry-${new Date().toISOString().replace(/[:.]/g, '-')}.png`)
  await page.screenshot({ path: shot, fullPage: false })
  writeFileSync(path.join(OUT_DIR, 'latest.png'), await page.screenshot({ fullPage: false }))

  await browser.close()
  return { checks, screenshot: shot, childPid }
}

// ───────────────────────── 主流程 ─────────────────────────

async function main() {
  const args = parseArgs(process.argv.slice(2))
  mkdirSync(OUT_DIR, { recursive: true })

  const t0 = Date.now()
  let child = null
  let token = args.token || process.env.DSH_TOKEN || null
  let startedByUs = false
  let reused = false

  const cleanup = () => {
    if (child && !args.keep) {
      killTree(child.pid)
      child = null
    }
  }
  process.on('SIGINT', () => { cleanup(); process.exit(130) })

  try {
    const p0 = await probe(`${args.url}/`)

    if (p0.up) {
      reused = true
      if (!token) {
        throw new Error(
          `${args.url} 已在运行但需要启动 token。\n` +
          `  任选其一：① 关掉它让脚本自己拉起（默认行为）  ② --token <启动日志里的 token>`,
        )
      }
    } else {
      if (!args.start) throw new Error(`${args.url} 未监听，且指定了 --no-start`)
      process.stdout.write(C.dim('· 3080 未监听，正在启动 dsh Web UI…\n'))
      const r = await startServer(args)
      child = r.child
      token = r.token
      startedByUs = true
      process.stdout.write(C.dim(`· 服务已就绪（pid ${child.pid}）\n`))
    }

    const { checks, screenshot } = await verifyInBrowser(args, token, child?.pid)
    const passed = checks.filter((c) => c.pass).length
    const allPass = passed === checks.length

    if (args.json) {
      console.log(JSON.stringify({
        ok: allPass,
        url: args.url,
        startedByUs, reused,
        checks, screenshot,
        elapsedMs: Date.now() - t0,
      }, null, 2))
    } else {
      console.log('')
      console.log(C.bold('  入口验证结果'))
      console.log('  ' + '─'.repeat(52))
      for (const c of checks) {
        const mark = c.pass ? C.ok('✔') : C.bad('✘')
        console.log(`  ${mark} ${c.name}${c.detail ? C.dim('  — ' + c.detail) : ''}`)
      }
      console.log('  ' + '─'.repeat(52))
      console.log(`  ${allPass ? C.ok('通过') : C.bad('失败')}  ${passed}/${checks.length}   耗时 ${((Date.now() - t0) / 1000).toFixed(1)}s`)
      console.log(`  截图  ${screenshot}`)
      if (reused) console.log(C.dim('  说明：复用了已在运行的服务'))
      if (child && args.keep) console.log(C.dim(`  服务保留在 ${args.url}（pid ${child.pid}），Ctrl+C 或 taskkill 关闭`))
      console.log('')
    }

    cleanup()
    process.exit(allPass ? 0 : 1)
  } catch (e) {
    cleanup()
    if (args.json) console.log(JSON.stringify({ ok: false, error: String(e.message || e) }, null, 2))
    else {
      console.error('')
      console.error(C.bad('  验证失败：') + String(e.message || e))
      console.error('')
    }
    process.exit(1)
  }
}

main()
