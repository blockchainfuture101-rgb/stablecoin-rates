#!/usr/bin/env python3
"""
穩定幣理財年化率抓取腳本
每 2 小時由 GitHub Actions 自動執行
輸出: data/rates.json
"""

import requests
import json
import time
import os
from datetime import datetime, timezone

# 目標穩定幣清單
STABLECOINS = {'USDT', 'USDC', 'BUSD', 'FDUSD', 'TUSD', 'DAI', 'PYUSD', 'USDE', 'SUSD'}

TIMEOUT = 15
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json',
}


# ─────────────────────────────────────────
# MEXC
# ─────────────────────────────────────────
def fetch_mexc():
    results = []

    # 嘗試 MEXC 活期理財
    endpoints = [
        "https://www.mexc.com/api/platform/spot/financial-products/list",
        "https://api.mexc.com/api/v3/savings/lending/daily/productList",
    ]

    for url in endpoints:
        try:
            params = {"pageNum": 1, "pageSize": 200, "status": "SUBSCRIBABLE"}
            r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            data = r.json()
            items = []

            # 格式 A: {"code":200, "data":{"list":[...]}}
            if data.get('code') in (200, '200') and isinstance(data.get('data'), dict):
                items = data['data'].get('list', data['data'].get('records', []))
            # 格式 B: {"code":"200000", "data":{"list":[...]}}
            elif isinstance(data.get('data'), list):
                items = data['data']

            for item in items:
                currency = (item.get('currency') or item.get('asset') or '').upper()
                if currency not in STABLECOINS:
                    continue
                apy_raw = item.get('annualizedRate') or item.get('annualInterestRate') or item.get('latestAnnualPercentageRate') or 0
                apy = float(apy_raw) * 100
                duration = item.get('productDuration') or item.get('duration') or 0
                results.append({
                    'currency': currency,
                    'apy': round(apy, 2),
                    'type': '定期' if int(duration) > 0 else '活期',
                    'duration': f"{duration}天" if int(duration) > 0 else '活期',
                    'min_amount': str(item.get('minAmount') or item.get('minPurchaseAmount') or '-'),
                    'product_name': item.get('productName') or ('定期儲蓄' if int(duration) > 0 else '活期儲蓄'),
                    'link': 'https://www.mexc.com/earn',
                })

            if results:
                print(f"  [MEXC] ✓ {len(results)} 個產品 (來源: {url})")
                return results

        except Exception as e:
            print(f"  [MEXC] ✗ {url} -> {e}")
            continue

    print("  [MEXC] ⚠ 所有端點失敗，回傳空陣列")
    return results


# ─────────────────────────────────────────
# Binance
# ─────────────────────────────────────────
def fetch_binance():
    results = []

    # 活期 Simple Earn
    try:
        url = "https://www.binance.com/bapi/earn/v1/friendly/lending/daily/product/list"
        page = 1
        while True:
            params = {"status": "SUBSCRIBABLE", "pageSize": 100, "pageIndex": page}
            r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            data = r.json()
            if not data.get('success'):
                break
            items = data.get('data', {}).get('list', [])
            if not items:
                break
            for item in items:
                currency = (item.get('asset') or '').upper()
                if currency not in STABLECOINS:
                    continue
                apy = float(item.get('latestAnnualPercentageRate') or 0) * 100
                results.append({
                    'currency': currency,
                    'apy': round(apy, 2),
                    'type': '活期',
                    'duration': '活期',
                    'min_amount': str(item.get('minPurchaseAmount') or '-'),
                    'product_name': 'Simple Earn 活期',
                    'link': 'https://www.binance.com/en/earn',
                })
            page += 1
            if page > 5:
                break
    except Exception as e:
        print(f"  [Binance] 活期 ✗ {e}")

    # 定期 Simple Earn (PoS)
    try:
        url = "https://www.binance.com/bapi/earn/v1/friendly/pos/union"
        page = 1
        while True:
            params = {"pageSize": 100, "pageIndex": page, "status": "SUBSCRIBABLE"}
            r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            data = r.json()
            if not data.get('success'):
                break
            items = data.get('data', {}).get('list', [])
            if not items:
                break
            for item in items:
                currency = (item.get('asset') or '').upper()
                if currency not in STABLECOINS:
                    continue
                apy = float(item.get('annualInterestRate') or 0) * 100
                duration = item.get('duration') or 0
                results.append({
                    'currency': currency,
                    'apy': round(apy, 2),
                    'type': '定期',
                    'duration': f"{duration}天",
                    'min_amount': str(item.get('minPurchaseAmount') or '-'),
                    'product_name': f'Simple Earn 定期 {duration}天',
                    'link': 'https://www.binance.com/en/earn',
                })
            page += 1
            if page > 5:
                break
    except Exception as e:
        print(f"  [Binance] 定期 ✗ {e}")

    print(f"  [Binance] ✓ {len(results)} 個產品")
    return results


# ─────────────────────────────────────────
# OKX
# ─────────────────────────────────────────
def fetch_okx():
    results = []

    # 活期存幣 (Savings lending rate summary)
    try:
        url = "https://www.okx.com/api/v5/finance/savings/lending-rate-summary"
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        if data.get('code') == '0':
            for item in data.get('data', []):
                currency = (item.get('ccy') or '').upper()
                if currency not in STABLECOINS:
                    continue
                # OKX rate 是日利率，換算年化
                daily_rate = float(item.get('rate') or 0)
                apy = daily_rate * 365 * 100
                results.append({
                    'currency': currency,
                    'apy': round(apy, 2),
                    'type': '活期',
                    'duration': '活期',
                    'min_amount': '-',
                    'product_name': 'Simple Earn 活期',
                    'link': 'https://www.okx.com/earn',
                })
    except Exception as e:
        print(f"  [OKX] 活期 ✗ {e}")

    # 定期賺幣
    try:
        url = "https://www.okx.com/api/v5/finance/staking-defi/eth/product"
        # OKX structured products
        url2 = "https://www.okx.com/api/v5/finance/staking-defi/product"
        r = requests.get(url2, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        if data.get('code') == '0':
            for item in data.get('data', []):
                currency = (item.get('investData', [{}])[0].get('ccy') if item.get('investData') else '').upper()
                if currency not in STABLECOINS:
                    continue
                apy = float(item.get('apy') or 0) * 100
                duration = item.get('term') or '活期'
                results.append({
                    'currency': currency,
                    'apy': round(apy, 2),
                    'type': '定期' if str(duration).isdigit() else '活期',
                    'duration': f"{duration}天" if str(duration).isdigit() else str(duration),
                    'min_amount': '-',
                    'product_name': item.get('productName') or 'OKX Earn',
                    'link': 'https://www.okx.com/earn',
                })
    except Exception as e:
        print(f"  [OKX] 定期 ✗ {e}")

    print(f"  [OKX] ✓ {len(results)} 個產品")
    return results


# ─────────────────────────────────────────
# Bybit
# ─────────────────────────────────────────
def fetch_bybit():
    results = []

    for category in ['FlexibleSaving', 'FixedSaving']:
        try:
            url = "https://api.bybit.com/v5/earn/product/list"
            params = {"category": category}
            r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            data = r.json()
            if data.get('retCode') == 0:
                for item in data.get('result', {}).get('list', []):
                    currency = (item.get('coin') or '').upper()
                    if currency not in STABLECOINS:
                        continue
                    apy = float(item.get('estimateApr') or item.get('apr') or 0) * 100
                    duration = item.get('duration') or 0
                    is_flexible = (category == 'FlexibleSaving')
                    results.append({
                        'currency': currency,
                        'apy': round(apy, 2),
                        'type': '活期' if is_flexible else '定期',
                        'duration': '活期' if is_flexible else f"{duration}天",
                        'min_amount': str(item.get('minStakeAmount') or '-'),
                        'product_name': f"{'活期' if is_flexible else '定期'}儲蓄",
                        'link': 'https://www.bybit.com/en/earn/',
                    })
        except Exception as e:
            print(f"  [Bybit] {category} ✗ {e}")

    print(f"  [Bybit] ✓ {len(results)} 個產品")
    return results


# ─────────────────────────────────────────
# Gate.io
# ─────────────────────────────────────────
def fetch_gate():
    results = []

    # 活期 UniLend
    try:
        url = "https://api.gateio.ws/api/v4/earn/uni_lend/currencies"
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        for item in (data if isinstance(data, list) else []):
            currency = (item.get('currency') or '').upper()
            if currency not in STABLECOINS:
                continue
            # interest_rate 是日利率
            daily_rate = float(item.get('interest_rate') or 0)
            apy = daily_rate * 365 * 100
            results.append({
                'currency': currency,
                'apy': round(apy, 2),
                'type': '活期',
                'duration': '活期',
                'min_amount': str(item.get('min_lend_amount') or '-'),
                'product_name': 'UniLend 活期',
                'link': 'https://www.gate.io/earn',
            })
    except Exception as e:
        print(f"  [Gate.io] UniLend ✗ {e}")

    # 定期結構性產品
    try:
        url = "https://api.gateio.ws/api/v4/earn/structured_products"
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        for item in (data if isinstance(data, list) else []):
            currency = (item.get('currency') or '').upper()
            if currency not in STABLECOINS:
                continue
            apy = float(item.get('annualized_rate') or item.get('yield') or 0) * 100
            duration = item.get('investment_days') or item.get('period') or '-'
            results.append({
                'currency': currency,
                'apy': round(apy, 2),
                'type': '定期',
                'duration': f"{duration}天" if str(duration).isdigit() else str(duration),
                'min_amount': str(item.get('min_invest_amount') or '-'),
                'product_name': item.get('name') or '定期理財',
                'link': 'https://www.gate.io/earn',
            })
    except Exception as e:
        print(f"  [Gate.io] 定期 ✗ {e}")

    print(f"  [Gate.io] ✓ {len(results)} 個產品")
    return results


# ─────────────────────────────────────────
# HTX (火幣)
# ─────────────────────────────────────────
def fetch_htx():
    results = []

    endpoints = [
        "https://api.htx.com/v1/financial/productlist",
        "https://api.huobi.pro/v1/financial/productlist",
    ]

    for url in endpoints:
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            data = r.json()
            if data.get('status') == 'ok' or data.get('code') == 200:
                items = data.get('data') or []
                for item in items:
                    currency = (item.get('currency') or item.get('asset') or '').upper()
                    if currency not in STABLECOINS:
                        continue
                    apy = float(item.get('annualizedRate') or item.get('annualized_rate') or 0) * 100
                    duration = item.get('period') or item.get('duration') or 0
                    results.append({
                        'currency': currency,
                        'apy': round(apy, 2),
                        'type': '定期' if int(duration) > 0 else '活期',
                        'duration': f"{duration}天" if int(duration) > 0 else '活期',
                        'min_amount': str(item.get('minInvestAmount') or item.get('min_amount') or '-'),
                        'product_name': item.get('name') or ('定期理財' if int(duration) > 0 else '活期理財'),
                        'link': 'https://www.htx.com/earn/',
                    })
                if results:
                    print(f"  [HTX] ✓ {len(results)} 個產品 (來源: {url})")
                    return results
        except Exception as e:
            print(f"  [HTX] ✗ {url} -> {e}")
            continue

    # 備用：嘗試 HTX 活期 Lending
    try:
        url = "https://api.htx.com/v1/common/currencys"
        # 嘗試另一個 HTX earn 端點
        url2 = "https://status.htx.com/api/v2/earn/products"
        r = requests.get(url2, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        items = data.get('data') or data.get('list') or []
        for item in items:
            currency = (item.get('currency') or item.get('coin') or '').upper()
            if currency not in STABLECOINS:
                continue
            apy = float(item.get('apy') or item.get('annualizedRate') or 0)
            if apy < 1:
                apy *= 100
            duration = item.get('duration') or 0
            results.append({
                'currency': currency,
                'apy': round(apy, 2),
                'type': '定期' if int(duration) > 0 else '活期',
                'duration': f"{duration}天" if int(duration) > 0 else '活期',
                'min_amount': str(item.get('minAmount') or '-'),
                'product_name': item.get('name') or 'HTX Earn',
                'link': 'https://www.htx.com/earn/',
            })
    except Exception as e:
        print(f"  [HTX] 備用 ✗ {e}")

    print(f"  [HTX] {'✓' if results else '⚠'} {len(results)} 個產品")
    return results


# ─────────────────────────────────────────
# KuCoin
# ─────────────────────────────────────────
def fetch_kucoin():
    results = []

    # 活期 Demand
    try:
        url = "https://api.kucoin.com/api/v2/project/list"
        params = {"type": "DEMAND_TYPE", "status": "PROCESSING"}
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        if data.get('code') == '200000':
            items = data.get('data', {})
            if isinstance(items, dict):
                items = items.get('items', [])
            for item in (items or []):
                currency = (item.get('currency') or '').upper()
                if currency not in STABLECOINS:
                    continue
                # interestRate 是日利率
                daily_rate = float(item.get('interestRate') or 0)
                apy = daily_rate * 365 * 100
                results.append({
                    'currency': currency,
                    'apy': round(apy, 2),
                    'type': '活期',
                    'duration': '活期',
                    'min_amount': str(item.get('minPurchaseSize') or '-'),
                    'product_name': 'KuCoin Earn 活期',
                    'link': 'https://www.kucoin.com/earn',
                })
    except Exception as e:
        print(f"  [KuCoin] 活期 ✗ {e}")

    # 定期 Fixed
    try:
        url = "https://api.kucoin.com/api/v2/project/list"
        params = {"type": "TIME_TYPE", "status": "PROCESSING"}
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        if data.get('code') == '200000':
            items = data.get('data', {})
            if isinstance(items, dict):
                items = items.get('items', [])
            for item in (items or []):
                currency = (item.get('currency') or '').upper()
                if currency not in STABLECOINS:
                    continue
                apy = float(item.get('interestRate') or 0) * 100
                duration = item.get('term') or item.get('duration') or '-'
                results.append({
                    'currency': currency,
                    'apy': round(apy, 2),
                    'type': '定期',
                    'duration': f"{duration}天" if str(duration).isdigit() else str(duration),
                    'min_amount': str(item.get('minPurchaseSize') or '-'),
                    'product_name': f'KuCoin Earn 定期',
                    'link': 'https://www.kucoin.com/earn',
                })
    except Exception as e:
        print(f"  [KuCoin] 定期 ✗ {e}")

    print(f"  [KuCoin] ✓ {len(results)} 個產品")
    return results


# ─────────────────────────────────────────
# Bitget
# ─────────────────────────────────────────
def fetch_bitget():
    results = []

    # 活期
    try:
        url = "https://api.bitget.com/api/v2/earn/savings/product"
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        if data.get('code') == '00000':
            for item in data.get('data', []):
                currency = (item.get('coin') or item.get('currency') or '').upper()
                if currency not in STABLECOINS:
                    continue
                apy_str = str(item.get('apyStr') or item.get('apy') or '0').replace('%', '')
                try:
                    apy = float(apy_str)
                    if apy < 1:
                        apy *= 100  # 如果是小數格式就換算
                except:
                    apy = 0.0
                results.append({
                    'currency': currency,
                    'apy': round(apy, 2),
                    'type': '活期',
                    'duration': '活期',
                    'min_amount': str(item.get('minStepAmount') or item.get('minAmount') or '-'),
                    'product_name': 'Bitget Earn 活期',
                    'link': 'https://www.bitget.com/earn/',
                })
    except Exception as e:
        print(f"  [Bitget] 活期 ✗ {e}")

    # 定期
    try:
        url = "https://api.bitget.com/api/v2/earn/fixed-products"
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        if data.get('code') == '00000':
            for item in data.get('data', []):
                currency = (item.get('coin') or '').upper()
                if currency not in STABLECOINS:
                    continue
                apy_str = str(item.get('apyStr') or item.get('apy') or '0').replace('%', '')
                try:
                    apy = float(apy_str)
                    if apy < 1:
                        apy *= 100
                except:
                    apy = 0.0
                duration = item.get('duration') or item.get('term') or '-'
                results.append({
                    'currency': currency,
                    'apy': round(apy, 2),
                    'type': '定期',
                    'duration': f"{duration}天" if str(duration).isdigit() else str(duration),
                    'min_amount': str(item.get('minAmount') or '-'),
                    'product_name': f'Bitget Earn 定期',
                    'link': 'https://www.bitget.com/earn/',
                })
    except Exception as e:
        print(f"  [Bitget] 定期 ✗ {e}")

    print(f"  [Bitget] ✓ {len(results)} 個產品")
    return results


# ─────────────────────────────────────────
# BingX
# ─────────────────────────────────────────
def fetch_bingx():
    results = []

    # 活期
    try:
        url = "https://open-api.bingx.com/openApi/walletFinance/v1/earn/productList"
        params = {"productType": "CURRENT"}
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        items = []
        if data.get('code') == 0:
            items = data.get('data', {})
            if isinstance(items, dict):
                items = items.get('list', [])
        for item in (items or []):
            currency = (item.get('asset') or item.get('currency') or '').upper()
            if currency not in STABLECOINS:
                continue
            apy = float(item.get('apy') or item.get('annualizedRate') or 0)
            if apy < 1:
                apy *= 100
            results.append({
                'currency': currency,
                'apy': round(apy, 2),
                'type': '活期',
                'duration': '活期',
                'min_amount': str(item.get('minAmount') or '-'),
                'product_name': 'BingX Earn 活期',
                'link': 'https://bingx.com/en-us/earn/',
            })
    except Exception as e:
        print(f"  [BingX] 活期 ✗ {e}")

    # 定期
    try:
        url = "https://open-api.bingx.com/openApi/walletFinance/v1/earn/productList"
        params = {"productType": "FIXED"}
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        data = r.json()
        items = []
        if data.get('code') == 0:
            items = data.get('data', {})
            if isinstance(items, dict):
                items = items.get('list', [])
        for item in (items or []):
            currency = (item.get('asset') or item.get('currency') or '').upper()
            if currency not in STABLECOINS:
                continue
            apy = float(item.get('apy') or 0)
            if apy < 1:
                apy *= 100
            duration = item.get('duration') or item.get('term') or '-'
            results.append({
                'currency': currency,
                'apy': round(apy, 2),
                'type': '定期',
                'duration': f"{duration}天" if str(duration).isdigit() else str(duration),
                'min_amount': str(item.get('minAmount') or '-'),
                'product_name': 'BingX Earn 定期',
                'link': 'https://bingx.com/en-us/earn/',
            })
    except Exception as e:
        print(f"  [BingX] 定期 ✗ {e}")

    print(f"  [BingX] ✓ {len(results)} 個產品")
    return results


# ─────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────
def main():
    print("=" * 50)
    print("穩定幣年化率抓取開始")
    print(f"時間: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 50)

    fetchers = {
        'Binance': fetch_binance,
        'OKX':     fetch_okx,
        'Bybit':   fetch_bybit,
        'Gate.io': fetch_gate,
        'HTX':     fetch_htx,
        'KuCoin':  fetch_kucoin,
        'Bitget':  fetch_bitget,
        'BingX':   fetch_bingx,
    }

    output = {
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'mexc': [],
        'others': {},
    }

    # 抓 MEXC（主角）
    print("\n>>> MEXC")
    output['mexc'] = fetch_mexc()
    time.sleep(0.8)

    # 抓競品
    for name, fn in fetchers.items():
        print(f"\n>>> {name}")
        try:
            output['others'][name] = fn()
        except Exception as e:
            print(f"  [{name}] ✗ 未預期錯誤: {e}")
            output['others'][name] = []
        time.sleep(0.5)

    # 統計
    total_mexc = len(output['mexc'])
    total_others = sum(len(v) for v in output['others'].values())
    print(f"\n{'='*50}")
    print(f"完成！MEXC: {total_mexc} 個 | 競品合計: {total_others} 個")

    # 儲存
    os.makedirs('data', exist_ok=True)
    path = os.path.join('data', 'rates.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"資料已儲存至 {path}")


if __name__ == '__main__':
    main()
