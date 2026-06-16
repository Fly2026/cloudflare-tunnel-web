#!/usr/bin/env python3
"""阿里云 DNS 自动化脚本

使用 Python3 标准库直接调用阿里云 DNS OpenAPI，为每个服务子域名
添加或更新 CNAME 记录，指向 Cloudflare Tunnel。

依赖：仅 Python3 标准库（urllib, hmac, hashlib, base64, json 等）
"""

import argparse
import base64
import hmac
import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone


ENDPOINT = "https://alidns.aliyuncs.com"


def sign(access_key_secret: str, parameters: dict) -> str:
    """生成阿里云 V1.0 HMAC-SHA1 签名。"""
    sorted_params = sorted(parameters.items())
    # 使用 quote_via=quote 而不是默认 quote_plus，确保空格编码为 %20
    canonical_query = urllib.parse.urlencode(sorted_params, quote_via=urllib.parse.quote)
    # 对 canonical query 再次编码，参与待签名字符串
    encoded_query = urllib.parse.quote(canonical_query, safe="")
    string_to_sign = f"GET&{urllib.parse.quote('/', safe='')}&{encoded_query}"
    key = f"{access_key_secret}&".encode("utf-8")
    raw_hmac = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(raw_hmac).decode("utf-8")


def build_url(access_key_id: str, access_key_secret: str, action: str, params: dict) -> str:
    """构造带签名的完整请求 URL。"""
    common = {
        "Format": "JSON",
        "Version": "2015-01-09",
        "AccessKeyId": access_key_id,
        "SignatureMethod": "HMAC-SHA1",
        "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "SignatureVersion": "1.0",
        "SignatureNonce": str(uuid.uuid4()),
        "Action": action,
    }
    all_params = {**common, **params}
    all_params["Signature"] = sign(access_key_secret, all_params)
    query = urllib.parse.urlencode(sorted(all_params.items()))
    return f"{ENDPOINT}/?{query}"


def request(url: str) -> dict:
    """发送 GET 请求并解析 JSON 响应。"""
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def describe_records(access_key_id: str, access_key_secret: str, domain: str, rr: str) -> list:
    """查询指定域名的 CNAME 解析记录。"""
    url = build_url(
        access_key_id,
        access_key_secret,
        "DescribeDomainRecords",
        {
            "DomainName": domain,
            "RRKeyWord": rr,
            "Type": "CNAME",
        },
    )
    data = request(url)
    records = data.get("DomainRecords", {}).get("Record", [])
    return [r for r in records if r.get("RR") == rr and r.get("Type") == "CNAME"]


def add_record(access_key_id: str, access_key_secret: str, domain: str, rr: str, value: str) -> dict:
    """添加 CNAME 记录。"""
    url = build_url(
        access_key_id,
        access_key_secret,
        "AddDomainRecord",
        {
            "DomainName": domain,
            "RR": rr,
            "Type": "CNAME",
            "Value": value,
            "TTL": "600",
        },
    )
    return request(url)


def update_record(access_key_id: str, access_key_secret: str, record_id: str, rr: str, value: str) -> dict:
    """更新 CNAME 记录。"""
    url = build_url(
        access_key_id,
        access_key_secret,
        "UpdateDomainRecord",
        {
            "RecordId": record_id,
            "RR": rr,
            "Type": "CNAME",
            "Value": value,
            "TTL": "600",
        },
    )
    return request(url)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="CFWEB 阿里云 DNS CNAME 自动化")
    parser.add_argument("--access-key", required=True, help="阿里云 AccessKey ID")
    parser.add_argument("--access-secret", required=True, help="阿里云 AccessKey Secret")
    parser.add_argument("--domain", required=True, help="根域名，如 example.com")
    parser.add_argument("--cname-target", required=True, help="Cloudflare Tunnel CNAME 目标，如 <tunnel-id>.cfargotunnel.com")
    parser.add_argument("--config", required=True, help="CFWEB config.json 路径")
    args = parser.parse_args()

    config = load_config(args.config)
    services = config.get("services", [])
    if not services:
        print("[CFWEB-DNS] 警告: config.json 中未定义任何服务", file=sys.stderr)
        return 0

    ok = True
    for svc in services:
        folder = svc.get("folder", "").strip()
        if not folder:
            print("[CFWEB-DNS] 跳过: folder 为空", file=sys.stderr)
            ok = False
            continue

        subdomain = f"{folder}.{args.domain}"
        print(f"[CFWEB-DNS] 处理: {subdomain} -> {args.cname_target}")

        try:
            records = describe_records(args.access_key, args.access_secret, args.domain, folder)
            if records:
                record_id = records[0]["RecordId"]
                update_record(args.access_key, args.access_secret, record_id, folder, args.cname_target)
                print(f"  已更新记录: {subdomain}")
            else:
                add_record(args.access_key, args.access_secret, args.domain, folder, args.cname_target)
                print(f"  已添加记录: {subdomain}")
        except Exception as exc:
            print(f"  错误: {exc}", file=sys.stderr)
            ok = False

    if ok:
        print("[CFWEB-DNS] DNS 配置完成")
        return 0
    print("[CFWEB-DNS] DNS 配置部分失败", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
