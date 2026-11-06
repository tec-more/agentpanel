# AI Panel Admin 前端

基于 Vue3 + Element Plus 的后台管理系统前端。

## 技术栈

- Vue 3.4
- Vue Router 4
- Pinia 状态管理
- Element Plus UI 组件库
- Axios 请求库
- Vite 构建工具
- Sass 样式预处理

## 环境要求

- Node.js >= 16.0
- npm >= 8.0 或 pnpm >= 7.0

## 安装依赖

```bash
cd web
npm install
```

或使用 pnpm：

```bash
pnpm install
```

## 开发运行

```bash
npm run dev
```

启动后访问：http://localhost:3000

> 开发模式下，API 请求会自动代理到后端 http://127.0.0.1:9999

## 生产构建

```bash
npm run build
```

构建产物在 `dist` 目录。

## 预览构建结果

```bash
npm run preview
```

## 项目结构

```
src/
├── api/                    # API 接口模块
│   ├── auth.js            # 认证相关接口
│   ├── user.js            # 用户管理接口
│   └── department.js      # 部门管理接口
├── assets/                 # 静态资源
│   └── logo.svg
├── components/             # 公共组件
├── layouts/                # 布局组件
│   └── MainLayout.vue     # 主布局（侧边栏+顶栏）
├── router/                 # 路由配置
│   └── index.js
├── stores/                 # Pinia 状态管理
│   └── user.js            # 用户状态
├── styles/                 # 全局样式
│   └── index.scss
├── utils/                  # 工具函数
│   └── request.js         # Axios 封装
├── views/                  # 页面组件
│   ├── auth/              # 认证模块
│   │   └── Login.vue      # 登录页
│   ├── dashboard/         # 仪表盘
│   │   └── Index.vue
│   ├── user/              # 用户管理
│   │   └── Index.vue
│   ├── department/        # 部门管理
│   │   └── Index.vue
│   └── NotFound.vue       # 404 页面
├── App.vue                 # 根组件
└── main.js                 # 应用入口
```

## 功能模块

### 认证模块
- 用户登录
- 用户注册
- 修改密码
- 退出登录

### 仪表盘
- 统计数据展示
- 快速入口
- 个人信息展示

### 用户管理
- 用户列表（分页、搜索）
- 新增用户
- 编辑用户
- 删除用户
- 启用/禁用用户

### 部门管理
- 部门列表（树形结构）
- 新增部门
- 添加子部门
- 编辑部门
- 删除部门

## 配置说明

### 开发代理配置

修改 `vite.config.js` 中的 proxy 配置：

```js
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:9999',  // 后端地址
      changeOrigin: true
    }
  }
}
```

### 生产环境配置

创建 `.env.production` 文件：

```
VITE_API_BASE_URL=https://your-api-domain.com/api
```

## 注意事项

1. 确保后端服务已启动并运行在 9999 端口
2. 首次运行需要先安装依赖
3. 登录后 Token 存储在 localStorage 中
4. API 响应格式需符合 `{ code: 200, data: {}, msg: '' }` 结构
