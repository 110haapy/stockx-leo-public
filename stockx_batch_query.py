import streamlit as st
import requests
import pandas as pd
import time
import plotly.express as px
from typing import List, Dict
import io

# -------------------------- 配置区 --------------------------
BASE_URL = "https://api.spiderx.cc/api/stockx"
QUERY_DELAY = 2.5  # 避免限流
TARGET_SIZE = "US 9"  # 你要查询的目标尺码

# -------------------------- 核心函数 --------------------------
def get_token():
    return st.secrets.get("STOCKX_TOKEN", "")

def get_auth():
    return "lis460225@gmail.com"

def validate_token(token: str) -> bool:
    try:
        res = requests.get(f"{BASE_URL}/ping", params={"token": token}, timeout=10)
        return res.status_code == 200
    except Exception as e:
        st.error(f"Token验证异常：{str(e)}")
        return False

def search_product_enhanced(style_id: str) -> Dict:
    """第一步：搜索商品，获取 productId"""
    token, auth = get_token(), get_auth()
    debug_info = {"步骤": "搜索商品"}
    
    try:
        res = requests.get(
            f"{BASE_URL}/search_product",
            params={
                "token": token,
                "auth": auth,
                "keyword": style_id,
                "page": 1,
                "country": "HK",
                "category": "sneakers",
                "currency_code": "USD"
            },
            timeout=20
        )
        
        debug_info["状态码"] = res.status_code
        debug_info["原始返回"] = res.text[:1500]
        if res.status_code != 200:
            return {"货号": style_id, "状态": f"搜索失败 {res.status_code}", "调试信息": str(debug_info)}
        
        data_root = res.json().get("data", {})
        products = data_root.get("Featured", []) or data_root.get("Results", [])
        
        if not products:
            return {"货号": style_id, "状态": "未找到商品", "调试信息": str(debug_info)}
        
        # 优先精确匹配 Style ID
        matched = next((p for p in products if str(p.get("styleId", "")).strip().upper() == style_id.strip().upper()), products[0])
        return {
            "货号": style_id,
            "状态": "查询成功",
            "商品ID": matched.get("id"),
            "商品名称": matched.get("title", ""),
            "调试信息": str(debug_info)
        }
    except Exception as e:
        return {"货号": style_id, "状态": f"异常：{str(e)}", "调试信息": str(debug_info)}

def get_product_detail(product_id: str) -> Dict:
    """第二步【关键新增】：获取商品详情，提取目标尺码的 product_uuid"""
    token, auth = get_token(), get_auth()
    debug_info = {"步骤": "获取商品详情", "商品ID": product_id}
    
    try:
        res = requests.get(
            f"{BASE_URL}/product_detail",
            params={
                "token": token,
                "auth": auth,
                "productId": product_id,
                "country": "HK",
                "currency_code": "USD"
            },
            timeout=20
        )
        
        debug_info["状态码"] = res.status_code
        debug_info["原始返回"] = res.text[:2000]
        if res.status_code != 200:
            return {"uuid": "", "尺码信息": "获取失败", "调试信息": str(debug_info)}
        
        data = res.json().get("data", {})
        sizes = data.get("sizes", [])  # 文档核心字段：sizes 数组包含所有尺码的 uuid
        
        # 查找目标尺码的 uuid
        target_uuid = ""
        for size in sizes:
            if size.get("size") == TARGET_SIZE:
                target_uuid = size.get("uuid", "")
                break
        
        return {
            "uuid": target_uuid,
            "尺码信息": f"找到 {TARGET_SIZE} 对应 UUID: {target_uuid[:10]}..." if target_uuid else "未找到目标尺码",
            "调试信息": str(debug_info)
        }
    except Exception as e:
        return {"uuid": "", "尺码信息": f"异常：{str(e)}", "调试信息": str(debug_info)}

def get_market_data(uuid: str) -> Dict:
    """第三步【官方推荐】：用 uuid 查询市场数据（替代旧的 market_info）"""
    token, auth = get_token(), get_auth()
    debug_info = {"步骤": "查询市场数据", "UUID": uuid[:10] + "..."}
    
    if not uuid:
        return {"最新成交价": 0, "最低挂售价": 0, "成交量": 0, "市场状态": "无UUID", "调试信息": str(debug_info)}
    
    try:
        # 官方推荐接口：product_size_activity_new（获取成交/挂售数据）
        res = requests.get(
            f"{BASE_URL}/product_size_activity_new",
            params={
                "token": token,
                "auth": auth,
                "product_uuid": uuid,
                "country": "HK",
                "currency_code": "USD"
            },
            timeout=25
        )
        
        debug_info["状态码"] = res.status_code
        debug_info["原始返回"] = res.text[:1500]
        if res.status_code != 200:
            return {"最新成交价": 0, "最低挂售价": 0, "成交量": 0, "市场状态": f"接口失败 {res.status_code}", "调试信息": str(debug_info)}
        
        data = res.json().get("data", {})
        # 解析官方文档标准返回字段
        last_sale = data.get("lastSale", {}).get("price", 0)
        lowest_ask = data.get("lowestAsk", {}).get("price", 0)
        sales_volume = len(data.get("sales", []))  # 成交记录数即为成交量
        
        return {
            "最新成交价": last_sale,
            "最低挂售价": lowest_ask,
            "成交量": sales_volume,
            "市场状态": "正常",
            "调试信息": str(debug_info)
        }
    except Exception as e:
        return {"最新成交价": 0, "最低挂售价": 0, "成交量": 0, "市场状态": f"异常：{str(e)}", "调试信息": str(debug_info)}

def batch_query(style_id_list: List[str]) -> List[Dict]:
    """批量执行完整链路"""
    results = []
    total = len(style_id_list)
    progress = st.progress(0)
    status = st.empty()

    for idx, sid in enumerate(style_id_list):
        sid = sid.strip()
        if not sid:
            continue
        status.text(f"处理中 {idx+1}/{total}：{sid}")
        
        # 步骤1：搜索商品
        step1 = search_product_enhanced(sid)
        if step1["状态"] != "查询成功":
            results.append({**step1, "最新成交价": 0, "最低挂售价": 0, "成交量": 0, "尺码信息": ""})
            progress.progress((idx+1)/total)
            time.sleep(QUERY_DELAY)
            continue
        
        # 步骤2：获取尺码 UUID（核心补全）
        step2 = get_product_detail(step1["商品ID"])
        
        # 步骤3：查询真实市场数据
        step3 = get_market_data(step2["uuid"])
        
        # 合并结果
        combined_debug = f"【1】{step1['调试信息']}\n【2】{step2['调试信息']}\n【3】{step3['调试信息']}"
        results.append({
            "货号": sid,
            "状态": step1["状态"],
            "商品名称": step1["商品名称"],
            "尺码信息": step2["尺码信息"],
            "最新成交价": step3["最新成交价"],
            "最低挂售价": step3["最低挂售价"],
            "成交量": step3["成交量"],
            "市场状态": step3["市场状态"],
            "调试信息": combined_debug
        })
        
        progress.progress((idx+1)/total)
        time.sleep(QUERY_DELAY)

    progress.empty()
    status.text(f"✅ 完成！共处理 {len(results)} 个货号")
    return results

# -------------------------- Web界面 --------------------------
def main():
    st.set_page_config(page_title="StockX 批量分析（官方文档适配版）", layout="wide")
    st.title("📊 StockX 批量货号分析智能体（官方接口标准版）")
    st.caption(f"适配官方推荐接口 | 目标尺码：{TARGET_SIZE} | 完整 UUID 链路")

    with st.sidebar:
        st.header("⚙️ 配置")
        st.text(f"Token状态：{'✅ 已配置' if get_token() else '❌ 未配置'}")
        st.text(f"Auth：{get_auth()}")
        if st.button("🔍 验证Token"):
            st.success("✅ 有效") if validate_token(get_token()) else st.error("❌ 无效")
        st.info("📌 已修复：新增 product_detail 获取 UUID，使用官方推荐 activity_new 接口")

    st.divider()
    tab1, tab2 = st.tabs(["📝 手动输入", "📂 上传文件"])
    style_ids = []

    with tab1:
        text = st.text_area("货号（每行一个）", placeholder="cw2288-111\nDD0587-002")
        if text:
            style_ids = [x.strip() for x in text.split("\n") if x.strip()]

    with tab2:
        file = st.file_uploader("上传 TXT/CSV（第一列货号）", type=["txt", "csv"])
        if file:
            if file.name.endswith(".txt"):
                style_ids = [x.strip() for x in file.read().decode("utf-8").split("\n") if x.strip()]
            else:
                style_ids = pd.read_csv(file).iloc[:,0].astype(str).tolist()
            st.success(f"读取到 {len(style_ids)} 个货号")

    if st.button("🚀 开始批量分析", type="primary", disabled=not (get_token() and style_ids)):
        with st.spinner("执行完整数据链路..."):
            st.session_state["results"] = batch_query(style_ids)

    if "results" in st.session_state and st.session_state["results"]:
        df = pd.DataFrame(st.session_state["results"])
        
        # 1. 结果表格
        st.divider()
        st.header("📋 核心结果")
        show_cols = ["货号", "商品名称", "尺码信息", "最新成交价", "最低挂售价", "成交量", "市场状态"]
        st.dataframe(df[show_cols], use_container_width=True)

        # 2. 详细调试（展开查看）
        st.divider()
        st.header("🔍 全链路调试日志")
        for _, row in df.iterrows():
            with st.expander(f"货号：{row['货号']} | 状态：{row['市场状态']}"):
                st.code(row["调试信息"], language="json")

        # 3. 导出
        st.divider()
        st.header("💾 导出数据")
        csv_buf = io.StringIO()
        df.to_csv(csv_buf, index=False, encoding="utf-8-sig")
        st.download_button("📥 导出 CSV", csv_buf.getvalue(), f"StockX结果_{int(time.time())}.csv")

if __name__ == "__main__":
    main()
