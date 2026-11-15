#!/usr/bin/env python3
"""拆分灰度观察期只读巡检。

对应 `reports/ops/l3-split-p7-grayscale.md` §6 的每日/每周检查清单。
脚本只读取 HTTP 端点、docker 状态和 Redis 键，**不发起任何写操作**：
每周 G1-A/B/C 的 reserve/settle/release 会改动计量数据，属于人工抽查，
刻意不纳入自动巡检，避免巡检本身触发 R5/R7。

用法（仓库根目录执行）：
    .venv/Scripts/python.exe deploy/gateway/scripts/observe_check.py
    .venv/Scripts/python.exe deploy/gateway/scripts/observe_check.py --json
    .venv/Scripts/python.exe deploy/gateway/scripts/observe_check.py --append
    .venv/Scripts/python.exe deploy/gateway/scripts/observe_check.py --init-baseline

状态含义：
    PASS / FAIL（硬项失败）/ WARN（需人工判断并登记）/ SKIP（检查不可用）
退出码：存在 FAIL 返回 1，否则 0（WARN/SKIP 不影响退出码）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[3]
BASELINE_FILE = ROOT / "deploy/gateway/observation-baseline.json"
LOG_FILE = ROOT / "reports/ops/l3-split-p7-observation-log.md"
REDIS_PASSWORD_FILE = ROOT / "deploy/gateway/secrets/redis_password"

APP = "http://127.0.0.1:9998"
GW = "http://127.0.0.1:9999"
ORCH = "http://127.0.0.1:9100"
PROM = "http://127.0.0.1:9090"

CONTAINERS = (
    "agentpanel-app",
    "agentpanel-gateway",
    "agentpanel-orchestration",
)
JOBS = ("aipaneladmin", "gateway", "orchestration")
RULE_GROUP = "agentpanel_alerts"
EXPECTED_RULE_COUNT = 10
# 监控栈目前只启动 prometheus 单服务，这两个辅助组件 down 属已知预期。
EXPECTED_FIRING_JOBS = {"pushgateway", "node_exporter"}

ROW_START = "<!-- DAILY_ROWS_START -->"
ROW_END = "<!-- DAILY_ROWS_END -->"


def http(url: str, timeout: float = 6.0) -> Tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001 - 巡检需把任何网络异常转成状态而非崩溃
        return -1, "%s: %s" % (type(exc).__name__, exc)


def http_json(url: str, timeout: float = 6.0) -> Tuple[int, Optional[Any]]:
    code, body = http(url, timeout)
    if code != 200:
        return code, None
    try:
        return code, json.loads(body)
    except ValueError:
        return code, None


class Report:
    def __init__(self) -> None:
        self.rows: List[Dict[str, str]] = []

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.rows.append({"name": name, "status": status, "detail": detail})

    def count(self, status: str) -> int:
        return sum(1 for r in self.rows if r["status"] == status)

    @property
    def failed(self) -> bool:
        return self.count("FAIL") > 0

    @property
    def verdict(self) -> str:
        return "FAIL" if self.failed else ("WARN" if self.count("WARN") else "PASS")

    def abnormal_details(self) -> str:
        parts = [
            "%s %s%s" % (r["status"], r["name"], ("：" + r["detail"]) if r["detail"] else "")
            for r in self.rows
            if r["status"] in ("FAIL", "WARN")
        ]
        return "；".join(parts) if parts else "—"


def check_containers(rep: Report) -> None:
    try:
        proc = subprocess.run(
            ["docker", "ps", "--filter", "name=agentpanel-", "--format", "{{.Names}}|{{.Status}}"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as exc:  # noqa: BLE001
        rep.add("容器 healthy", "SKIP", "docker 不可用：%s" % type(exc).__name__)
        return
    if proc.returncode != 0:
        rep.add("容器 healthy", "SKIP", "docker ps 失败")
        return
    found = {}
    for line in proc.stdout.strip().splitlines():
        if "|" in line:
            name, _, status = line.partition("|")
            found[name.strip()] = status.strip()
    missing = [c for c in CONTAINERS if c not in found]
    unhealthy = [c for c, s in found.items() if c in CONTAINERS and "healthy" not in s]
    if missing or unhealthy:
        rep.add("容器 healthy", "FAIL", "缺失=%s 非healthy=%s" % (missing or "无", unhealthy or "无"))
    else:
        rep.add("容器 healthy", "PASS", "3/3 healthy")


def check_health(rep: Report) -> None:
    endpoints = (
        ("App /health/health", APP + "/health/health"),
        ("网关 /health", GW + "/health"),
        ("编排 /health/health", ORCH + "/health/health"),
        ("编排 /health/orchestration", ORCH + "/health/orchestration"),
    )
    for name, url in endpoints:
        code, _ = http(url)
        rep.add(name, "PASS" if code == 200 else "FAIL", "HTTP %s" % code)

    code, body = http(ORCH + "/health/orchestration")
    if code != 200:
        rep.add("编排 mode", "FAIL", "健康端点不可达")
        return
    try:
        payload = json.loads(body)
    except ValueError:
        rep.add("编排 mode", "FAIL", "响应非 JSON")
        return
    mode = payload.get("mode")
    if mode != "proxy":
        rep.add("编排 mode", "FAIL", "mode=%s（期望 proxy）" % mode)
    else:
        rep.add("编排 mode", "PASS", "mode=proxy, write_enabled=%s" % payload.get("write_enabled"))


def check_proxy(rep: Report) -> None:
    # 401 表示请求已到达编排并被内部鉴权拒绝；503 表示代理链路断裂（回切条件 R2）。
    targets = (
        ("App 代理可达", APP + "/api/v1/harness/runs/nope"),
        ("编排直连可达", ORCH + "/v1/harness/runs/nope"),
    )
    for name, url in targets:
        code, _ = http(url)
        if code == 401:
            rep.add(name, "PASS", "401（代理链路正常）")
        else:
            rep.add(name, "FAIL", "HTTP %s（期望 401；503 意味着代理断裂）" % code)


def _redis():
    import redis  # 延迟导入：缺少依赖时只影响配额检查

    password = REDIS_PASSWORD_FILE.read_text(encoding="utf-8").strip()
    client = redis.Redis(host="127.0.0.1", port=6379, password=password, db=0,
                         decode_responses=True, socket_timeout=5)
    client.ping()
    return client


def collect_quota(client) -> Dict[str, Dict[str, str]]:
    used, held = {}, {}
    for key in sorted(client.keys("quota:*")):
        used[key] = str(client.get(key))
    for key in sorted(client.keys("quota_held:*")):
        held[key] = str(client.get(key))
    return {"used": used, "held": held}


def init_baseline() -> int:
    try:
        client = _redis()
        snapshot = collect_quota(client)
    except Exception as exc:  # noqa: BLE001
        print("生成基线失败：%s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1
    payload = {
        "started_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "note": "观察期起算基线；used 变化需人工判断是否业务请求导致，再更新本文件",
        "mode": "proxy",
        "quota_used": snapshot["used"],
        "quota_held": snapshot["held"],
        "quota_holds_index": [],
    }
    BASELINE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("基线已写入 %s" % BASELINE_FILE)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _load_baseline() -> Optional[Dict[str, Any]]:
    if not BASELINE_FILE.exists():
        return None
    try:
        return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def check_quota(rep: Report) -> None:
    baseline = _load_baseline()
    try:
        client = _redis()
        current = collect_quota(client)
        holds = client.zrange("quota_holds_index", 0, -1)
    except Exception as exc:  # noqa: BLE001
        rep.add("配额 Redis 可读", "FAIL", "%s: %s" % (type(exc).__name__, exc))
        return
    rep.add("配额 Redis 可读", "PASS", "used %d 键 / held %d 键" % (
        len(current["used"]), len(current["held"])))

    # R5：预占悬挂是硬失败。held 必须为 0，索引必须为空。
    nonzero = {k: v for k, v in current["held"].items() if float(v or 0) != 0}
    if nonzero or holds:
        rep.add("held 无悬挂", "FAIL", "nonzero=%s index=%s" % (nonzero or "无", holds or "空"))
    else:
        rep.add("held 无悬挂", "PASS", "held 全 0，quota_holds_index 空")

    # R7：used 变化不能自动判定违规（正常业务请求会写入），只提示人工登记。
    if baseline is None:
        rep.add("used 基线对比", "WARN", "未找到基线文件，请执行 --init-baseline")
        return
    expected = baseline.get("quota_used", {})
    diffs = []
    for key in sorted(set(expected) | set(current["used"])):
        old, new = expected.get(key), current["used"].get(key)
        if old != new:
            diffs.append("%s %s→%s" % (key, old if old is not None else "无", new if new is not None else "无"))
    if diffs:
        rep.add("used 基线对比", "WARN", "；".join(diffs) + "（需登记业务写入来源）")
    else:
        rep.add("used 基线对比", "PASS", "%d 个键与起算基线一致" % len(expected))


def check_metrics(rep: Report) -> None:
    for name, base, service in (
        ("网关 /metrics", GW, "gateway"),
        ("编排 /metrics", ORCH, "orchestration"),
    ):
        code, body = http(base + "/metrics")
        if code != 200:
            rep.add(name, "FAIL", "HTTP %s" % code)
            continue
        gauges = {}
        for line in body.splitlines():
            if line.startswith("health_check_status{"):
                metric, _, value = line.rpartition(" ")
                if 'service="%s"' % service in metric:
                    gauges[metric] = value.strip()
        bad = [v for v in gauges.values() if v not in ("1.0", "1")]
        if not gauges or bad:
            rep.add(name, "FAIL", "健康 Gauge 异常：%s" % (gauges or "无序列"))
        else:
            rep.add(name, "PASS", "200，健康 Gauge=%s" % ",".join(sorted(set(gauges.values()))))


def check_prometheus(rep: Report, enabled: bool) -> None:
    if not enabled:
        rep.add("Prometheus 抓取", "SKIP", "命令行指定跳过")
        return
    code, data = http_json(PROM + "/api/v1/targets?" + urllib.parse.urlencode({"state": "active"}))
    if code != 200 or data is None:
        rep.add("Prometheus 抓取", "WARN", "9090 不可达，需人工查看告警页")
        return
    jobs = {}
    for target in data.get("data", {}).get("activeTargets", []):
        jobs[target.get("labels", {}).get("job")] = target.get("health")
    bad = {j: jobs.get(j, "缺失") for j in JOBS if jobs.get(j) != "up"}
    rep.add("Prometheus 抓取", "FAIL" if bad else "PASS", str(bad) if bad else "3 个服务 job up")

    code, data = http_json(PROM + "/api/v1/rules")
    if code != 200 or data is None:
        rep.add("告警规则加载", "WARN", "规则接口不可达")
    else:
        groups = {g.get("name"): len(g.get("rules", [])) for g in data.get("data", {}).get("groups", [])}
        n = groups.get(RULE_GROUP, 0)
        rep.add("告警规则加载", "PASS" if n >= EXPECTED_RULE_COUNT else "FAIL",
                "%s=%d 条（不少于 %d；规则新增不视为失败）" % (RULE_GROUP, n, EXPECTED_RULE_COUNT))

    code, data = http_json(PROM + "/api/v1/alerts")
    if code != 200 or data is None:
        rep.add("非预期告警", "WARN", "告警接口不可达")
        return
    unexpected = []
    for alert in data.get("data", {}).get("alerts", []):
        if alert.get("state") != "firing":
            continue
        labels = alert.get("labels", {})
        if labels.get("job") in EXPECTED_FIRING_JOBS:
            continue
        unexpected.append("%s/%s" % (labels.get("alertname"), labels.get("job") or labels.get("instance")))
    rep.add("非预期告警", "FAIL" if unexpected else "PASS",
            "；".join(unexpected) if unexpected else "firing 均为已知辅助组件 down")


def build_report(with_prometheus: bool) -> Report:
    rep = Report()
    check_containers(rep)
    check_health(rep)
    check_proxy(rep)
    check_quota(rep)
    check_metrics(rep)
    check_prometheus(rep, with_prometheus)
    return rep


def print_table(rep: Report) -> None:
    now = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    print("灰度观察期巡检  %s" % now)
    print("-" * 92)
    print("%-28s %-6s %s" % ("检查项", "状态", "说明"))
    print("-" * 92)
    for row in rep.rows:
        print("%-28s %-6s %s" % (row["name"], row["status"], row["detail"]))
    print("-" * 92)
    print("结论 %s  PASS=%d FAIL=%d WARN=%d SKIP=%d" % (
        rep.verdict, rep.count("PASS"), rep.count("FAIL"), rep.count("WARN"), rep.count("SKIP")))


def append_log(rep: Report) -> None:
    if not LOG_FILE.exists():
        print("台账文件不存在，跳过追加：%s" % LOG_FILE, file=sys.stderr)
        return
    text = LOG_FILE.read_text(encoding="utf-8")
    if ROW_START not in text or ROW_END not in text:
        print("台账缺少行标记，跳过追加", file=sys.stderr)
        return
    day = dt.datetime.now().astimezone().strftime("%Y-%m-%d")
    stamp = dt.datetime.now().astimezone().strftime("%H:%M")
    row = "| %s | %s | 脚本 | %s (P%d/F%d/W%d/S%d) | %s |" % (
        day, stamp, rep.verdict,
        rep.count("PASS"), rep.count("FAIL"), rep.count("WARN"), rep.count("SKIP"),
        rep.abnormal_details().replace("|", "/"),
    )
    head, rest = text.split(ROW_START, 1)
    body, tail = rest.split(ROW_END, 1)
    lines = [ln for ln in body.splitlines() if ln.strip() and not ln.startswith("| " + day + " |")]
    new_body = "\n" + "\n".join(lines + [row]) + "\n"
    LOG_FILE.write_text(head + ROW_START + new_body + ROW_END + tail, encoding="utf-8")
    print("台账已追加/更新当日记录：%s" % row)


def main() -> int:
    parser = argparse.ArgumentParser(description="灰度观察期只读巡检")
    parser.add_argument("--json", action="store_true", help="只输出 JSON")
    parser.add_argument("--append", action="store_true", help="把结果写入观察期台账（当日去重）")
    parser.add_argument("--init-baseline", action="store_true", help="从当前 Redis 生成起算基线快照")
    parser.add_argument("--no-prometheus", action="store_true", help="跳过 Prometheus 检查")
    args = parser.parse_args()

    if args.init_baseline:
        return init_baseline()

    rep = build_report(not args.no_prometheus)
    if args.json:
        print(json.dumps({
            "checked_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "verdict": rep.verdict,
            "summary": {s: rep.count(s) for s in ("PASS", "FAIL", "WARN", "SKIP")},
            "checks": rep.rows,
        }, ensure_ascii=False, indent=2))
    else:
        print_table(rep)
    if args.append:
        append_log(rep)
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
