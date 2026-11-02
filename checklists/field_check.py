#!/usr/bin/env python3
"""信息完整性核对工具（EGO-A 本地构件）。

把"必需字段清单"从口头习惯落成可执行核对：
- 清单文件为 JSON：{"required": ["a","b","子对象.c"], "optional": ["d"], "forbid_extra": false}
- 字段路径用点号分隔，支持一层嵌套（如 "server.host"）
- 已知限制：required/optional 路径不支持列表索引（如 servers[0].host 会被判缺失）；
  显式 null 计为缺失；forbid_extra 检出的多余路径用方括号记号（servers[0].x），
  与规格文件的点号记号不一致；数据根不是对象时 forbid_extra 整体标记为 "$root"
- 用法：
    python checklists/field_check.py --spec <清单.json> --data <数据.json>
    python checklists/field_check.py --demo        # 内置自测
退出码：0=完整；1=缺失必需字段；2=规格/数据文件错误。
仅本地只读两个输入文件，不写入、不联网、不调用外部服务。
"""
from __future__ import annotations
import argparse, json, sys

DEMO_SPEC = {
    "name": "demo-required-fields",
    "description": "示例：请求外部合作方提供部署参数时应核对的字段",
    "required": ["server.host", "server.port", "auth.token", "retry.max_attempts"],
    "optional": ["auth.expires_at", "notes"],
    "forbid_extra": False,
}
DEMO_DATA_OK = {
    "server": {"host": "example.internal", "port": 8443},
    "auth": {"token": "xxx", "expires_at": "2027-01-01T00:00:00+08:00"},
    "retry": {"max_attempts": 3},
}
DEMO_DATA_MISSING = {
    "server": {"host": "example.internal"},
    "auth": {"token": "xxx"},
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_path(obj, dotted: str):
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def check(spec: dict, data: dict) -> dict:
    missing = [p for p in spec.get("required", []) if get_path(data, p) is None]
    present_optional = [p for p in spec.get("optional", []) if get_path(data, p) is not None]
    extra = []
    if spec.get("forbid_extra"):
        allowed = set(spec.get("required", [])) | set(spec.get("optional", []))
        if not isinstance(data, dict):
            # 数据根不是对象：内容无法用语义化的点号路径表达，整体标记为额外
            extra.append("$root")
        else:
            def walk(o, prefix=""):
                if prefix and prefix in allowed:
                    return  # 已允许路径的子树整体放行（修复：列表元素不再被误报为 extra）
                if isinstance(o, dict):
                    for k, v in o.items():
                        walk(v, f"{prefix}.{k}" if prefix else k)
                elif isinstance(o, list):
                    for i, v in enumerate(o):
                        walk(v, f"{prefix}[{i}]")
                else:
                    extra.append(prefix)
            walk(data)
    return {
        "complete": not missing,
        "missing_required": missing,
        "present_optional": present_optional,
        "unexpected_extra": extra,
    }


def demo() -> int:
    r_ok = check(DEMO_SPEC, DEMO_DATA_OK)
    r_bad = check(DEMO_SPEC, DEMO_DATA_MISSING)
    assert r_ok["complete"] is True, r_ok
    assert set(r_bad["missing_required"]) == {"server.port", "retry.max_attempts"}, r_bad
    print("DEMO PASS: complete-data 通过；缺字段数据被检出 server.port、retry.max_attempts")
    print(json.dumps({"ok_case": r_ok, "missing_case": r_bad}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="field_check")
    ap.add_argument("--spec")
    ap.add_argument("--data")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    if a.demo:
        return demo()
    if not a.spec or not a.data:
        ap.error("需要 --spec 与 --data（或 --demo）")
    try:
        spec = load_json(a.spec)
        data = load_json(a.data)
    except (OSError, json.JSONDecodeError) as ex:
        print(f"ERROR: 无法读取输入: {ex}", file=sys.stderr)
        return 2
    report = check(spec, data)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    sys.exit(main())
