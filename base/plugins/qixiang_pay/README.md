# 七相支付插件

七相聚合支付接口集成插件，支持微信支付和支付宝。

## 功能特性

- ✅ 支持支付宝和微信支付
- ✅ 自适应支付链接（PC端扫码/手机端H5自动识别）
- ✅ 无需企业资质（个人/个体户可申请）
- ✅ 简单的MD5签名（易于集成）
- ✅ 异步通知 + 主动查询双重确认

## 配置说明

### 1. 申请七相支付账号

1. 访问七相支付官网注册账号
2. 获取商户ID（PID）和商户密钥（KEY）
3. 测试账号：PID=1003，KEY需联系客服获取

### 2. 修改config.ini

在项目的config.ini文件中添加以下配置：

```ini
[qixiang_pay]
# 商户ID
pid = 1003

# 商户密钥
key = YOUR_KEY_HERE

# 统一下单接口
api_url = https://api.payqixiang.cn/mapi.php

# 查询订单接口
query_url = https://api.payqixiang.cn/api.php

# 异步通知地址（需要外网可访问）
notify_url = http://yourdomain.com/v1/qixiang/notify

# 跳转通知地址
return_url = http://yourdomain.com/payment/result
```

### 3. 重启服务

修改配置后需要重启FastAPI服务。

## API接口

### 1. 创建支付订单

**接口**: `POST /v1/qixiang/create`

**请求参数**:
```json
{
  "order_no": "20240327001",
  "pay_type": "alipay",
  "amount": 99.00,
  "subject": "VIP会员",
  "client_ip": "127.0.0.1",
  "param": ""
}
```

**响应示例**:
```json
{
  "code": 0,
  "msg": "创建订单成功",
  "data": {
    "order_no": "20240327001",
    "trade_no": "20240327001234567890",
    "payurl": "https://api.payqixiang.cn/pay/submit/xxx/",
    "qrcode": "weixin://wxpay/bizpayurl?pr=xxx",
    "pay_type": "alipay"
  }
}
```

**payurl使用方式**:
- PC端：生成二维码让用户扫描
- 手机端：直接跳转链接唤起支付

### 2. 查询订单状态

**接口**: `GET /v1/qixiang/query/{order_no}`

**响应示例**:
```json
{
  "code": 0,
  "msg": "查询成功",
  "data": {
    "order_no": "20240327001",
    "trade_no": "20240327001234567890",
    "status": "success",
    "pay_type": "alipay",
    "amount": 99.00,
    "trade_status": 1
  }
}
```

**状态说明**:
- `success`: 支付成功
- `pending`: 未支付
- `failed`: 支付失败

### 3. 支付异步回调

**接口**: `POST /v1/qixiang/notify`

由七相支付服务器主动调用，无需前端调用。

## 使用示例

### Python调用示例

```python
import httpx

async def create_qixiang_order():
    """创建七相支付订单"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/v1/qixiang/create",
            json={
                "order_no": "20240327001",
                "pay_type": "alipay",
                "amount": 0.01,
                "subject": "VIP会员"
            }
        )
        result = response.json()
        return result

async def query_qixiang_order(order_no: str):
    """查询七相支付订单"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"http://localhost:8000/v1/qixiang/query/{order_no}"
        )
        result = response.json()
        return result
```

### cURL调用示例

```bash
# 创建订单
curl -X POST "http://localhost:8000/v1/qixiang/create" \
  -H "Content-Type: application/json" \
  -d '{
    "order_no": "20240327001",
    "pay_type": "alipay",
    "amount": 0.01,
    "subject": "VIP会员"
  }'

# 查询订单
curl -X GET "http://localhost:8000/v1/qixiang/query/20240327001"
```

## 前端集成

### PC端扫码支付

```javascript
// 1. 创建订单获取支付链接
const response = await fetch('/v1/qixiang/create', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    order_no: '20240327001',
    pay_type: 'alipay',
    amount: 99.00,
    subject: 'VIP会员'
  })
});

const result = await response.json();
const payurl = result.data.payurl;

// 2. 生成二维码（使用qrcode.js库）
const qr = qrcode(0, 'L');
qr.addData(payurl);
qr.make();
document.getElementById('qrcode').innerHTML = qr.createImgTag();

// 3. 轮询查询支付状态
const pollTimer = setInterval(async () => {
  const res = await fetch(`/v1/qixiang/query/20240327001`);
  const data = await res.json();

  if (data.data.status === 'success') {
    clearInterval(pollTimer);
    alert('支付成功！');
    // 跳转到订单详情页
  }
}, 2000); // 每2秒查询一次
```

### 移动端H5支付

```javascript
// 1. 创建订单获取支付链接
const response = await fetch('/v1/qixiang/create', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    order_no: '20240327001',
    pay_type: 'alipay',
    amount: 99.00,
    subject: 'VIP会员'
  })
});

const result = await response.json();

// 2. 直接跳转到支付页面
window.location.href = result.data.payurl;
```

## 支付流程

### PC端扫码支付流程

```
1. 用户下单 → 调用create接口获取payurl
2. 后端生成二维码 → 展示给用户
3. 用户扫码支付 → 在手机上完成支付
4. 后端收到异步通知 → 更新订单状态
5. 前端轮询检测到success → 跳转到订单详情
```

### 移动端H5支付流程

```
1. 用户下单 → 调用create接口获取payurl
2. 前端跳转到payurl → 唤起支付宝/微信
3. 用户完成支付 → 返回return_url
4. 后端收到异步通知 → 更新订单状态
```

## 注意事项

### 1. 签名算法
- 参数按ASCII码排序（a-z）
- 排除sign、sign_type和空值
- MD5结果为小写

### 2. 回调处理
- 必须返回纯文本"success"
- trade_status是"TRADE_SUCCESS"才是成功
- 回调可能没有name参数，不参与签名

### 3. 订单号
- out_trade_no: 商户订单号（我们系统的）
- trade_no: 七相系统订单号
- 两个都要记录

### 4. 金额格式
- 单位是元，不是分
- 最多2位小数

### 5. device参数
- 统一下单时必须传"jump"
- 否则不会返回支付链接

## 测试

### 测试账号
- PID: 1003
- KEY: 联系七相支付客服获取

### 测试建议
- 使用小额金额测试（0.01元）
- 测试完成后当日退款

## 常见问题

### Q1: 创建订单失败？
检查配置项是否完整（pid、key、api_url）

### Q2: 回调收不到？
确保notify_url外网可访问，可以使用内网穿透工具

### Q3: 签名验证失败？
检查参数排序是否正确，空值是否被排除

### Q4: PC端显示二维码但手机不跳转？
确保device参数传的是"jump"

## 与官方支付插件对比

| 特性 | 七相支付 | 官方微信/支付宝 |
|------|---------|----------------|
| **资质要求** | 个人/个体户 | 企业资质 |
| **申请难度** | 简单 | 复杂 |
| **支付方式** | 微信+支付宝 | 单一支付方式 |
| **结算方式** | D+1到银行卡 | T+1对公 |
| **适用场景** | 个人开发者 | 企业商户 |

## 技术支持

- 七相支付文档: https://www.qixiangpay.cn/doc_old.html
- 七相支付客服: 联系官方客服

## 更新日志

### v1.0.0 (2026-03-27)
- 初始版本
- 支持支付宝和微信支付
- 实现统一下单、查询订单、异步回调
