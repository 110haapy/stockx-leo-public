import streamlit as st
import requests
import pandas as pd
import time
import io

# -------------------------- 配置 --------------------------
BASE_URL = "https://api.spiderx.cc/api/stockx"
TOKEN = st.secrets.get("STOCKX_TOKEN", "")
AUTH = "lis460225@gmail.com"
SIZE = "US 9"

# -------------------------- 1. 搜索商品 --------------------------
def search(style_id):
    try:
        r = requests.get(f"{BASE_URL}/search_product", params={
            "token": TOKEN,
            "auth": AUTH,
            "keyword": style_id,
            "country": "HK",
            "category": "sneakers",
            "currency_code": "USD"
        }, timeout=15)
        data = r.json()
        products = data.get("data", {}).get("Featured", []) or data.get("data", {}).get("Results", [])
        if not products:
            return {"error": "无商品"}
        return products[0].get("id")
    except:
        return None

# -------------------------- 2. 商品详情（取尺码UUID） --------------------------
def product_detail(product_id):
    try:
        r = requests.get(f"{BASE_URL}/product_detail", params={
            "token": TOKEN,
            "auth": AUTH,
            "product_id": product_id  # 文档明确：product_id
        }, timeout=15)
        data = r.json()
        variants = data.get("data", {}).get("sizeVariants", [])
        for v in variants:
            if v.get("size") == SIZE:
                return v.get("uuid")
        return None
    except:
        return None

# -------------------------- 3. 市场数据（文档标准接口） --------------------------
def market_data(uuid):
    try:
        r = requests.get(f"{BASE_URL}/product_size_activity_new", params={
            "token": TOKEN,
            "auth": AUTH,
            "productUuid": uuid  # 文档明确：productUuid
        }, timeout=15)
        data = r.json().get("data", {})
        last = data.get("lastSale", {}).get("price", 0)
        ask = data.get("lowestAsk", {}).get("price", 0)
        volume = len(data.get("sales", []))
        return last, ask, volume
    except:
        return 0,0,0

# -------------------------- 批量查询 --------------------------
def run(ids):
    rows = []
    for sid in ids:
        sid = sid.strip()
        if not sid: continue
        
        pid = search(sid)
        if not pid:
            rows.append([sid, "搜不到商品", 0,0,0])
            continue
        
        uuid = product_detail(pid)
        if not uuid:
            rows.append([sid, "无此尺码", 0,0,0])
            continue
        
        last, ask, vol = market_data(uuid)
        rows.append([sid, "成功", last, ask, vol])
        time.sleep(2)
    return rows

# -------------------------- 页面 --------------------------
st.title("StockX 查价工具（最终极简版）")
text = st.text_area("输入货号，每行一个")
if st.button("开始查询"):
    ids = text.split("\n")
    res = run(ids)
    df = pd.DataFrame(res, columns=["货号", "状态", "最新成交价", "最低卖价", "成交量"])
    st.dataframe(df)
