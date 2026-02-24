import streamlit as st
import requests
import pandas as pd
import time
import plotly.express as px
from typing import List, Dict
import io

# -------------------------- 配置区 --------------------------
BASE_URL = "https://api.spiderx.cc/api/stockx"
QUERY_DELAY = 2.5  # 延长延迟，避免API限流导致的空数据

# -------------------------- 核心函数 --------------------------
def get_token():
    """自动读取秘钥中的Token"""
    return st.secrets.get("STOCKX_TOKEN", "")

def validate_token(token: str) -> bool:
    """验证Token是否有效"""
    try:
        res = requests.get(f"{BASE_URL}/ping", params={"token": token}, timeout=10)
        return res.status_code == 200
    except Exception as e:
        st.error(f"Token验证异常：{str(e)}")
        return False

def search_product_enhanced(style_id: str) -> Dict:
    """强化版搜索：支持Style ID+强制关键词，同时返回调试信息"""
    token = get_token()
    # 调试用：存储API返回的原始数据
    debug_info = {}
    
    try:
        # 策略1：直接搜索Style ID（基础搜索）
        search_res = requests.get(
            f"{BASE_URL}/search",
            params={"q": style_id, "token": token},
            timeout=20
        )
        # 保存原始返回数据用于调试
        debug_info["搜索接口状态码"] = search_res.status_code
        debug_info["搜索接口原始返回"] = search_res.text[:500]  # 截取前500字符，避免页面过长
        
        if search_res.status_code != 200:
            return {
                "货号": style_id,
                "状态": f"API请求失败（状态码：{search_res.status_code}）",
                "商品ID": "",
                "商品名称": "",
                "调试信息": str(debug_info)
            }
        
        search_data = search_res.json()
        debug_info["解析后的搜索数据"] = search_data.get("data", [])[:2]  # 只看前2个结果
        
        # 策略2：如果基础搜索无结果，拼接"Air Jordan"关键词（DD0587-002是AJ系列）
        products = search_data.get("data", [])
        if not products:
            enhanced_q = f"Air Jordan {style_id}"
            st.warning(f"基础搜索无结果，尝试强化搜索：{enhanced_q}")
            search_res_enhanced = requests.get(
                f"{BASE_URL}/search",
                params={"q": enhanced_q, "token": token},
                timeout=20
            )
            debug_info["强化搜索状态码"] = search_res_enhanced.status_code
            debug_info["强化搜索原始返回"] = search_res_enhanced.text[:500]
            if search_res_enhanced.status_code == 200:
                products = search_res_enhanced.json().get("data", [])
        
        if not products:
            return {
                "货号": style_id,
                "状态": "未找到商品（基础+强化搜索均无结果）",
                "商品ID": "",
                "商品名称": "",
                "调试信息": str(debug_info)
            }
        
        # 优先精确匹配Style ID
        matched_product = None
        for p in products:
            # 兼容接口返回的styleId字段可能的大小写/空格问题
            if str(p.get("styleId", "")).strip().upper() == style_id.strip().upper():
                matched_product = p
                break
        # 无精确匹配则取第一个结果
        if not matched_product:
            matched_product = products[0]
            st.info(f"未找到精确匹配的Style ID，取第一个搜索结果：{matched_product.get('title', '未知')}")

        return {
            "货号": style_id,
            "状态": "查询成功",
            "商品ID": matched_product.get("id"),
            "商品名称": matched_product.get("title", ""),
            "调试信息": str(debug_info)  # 保留调试信息
        }
    except Exception as e:
        return {
            "货号": style_id,
            "状态": f"代码执行异常：{str(e)}",
            "商品ID": "",
            "商品名称": "",
            "调试信息": str(debug_info)
        }

def get_market_info(product_id: str) -> Dict:
    """获取销售信息（带异常捕获）"""
    token = get_token()
    try:
        res = requests.get(
            f"{BASE_URL}/product_market_info",
            params={"productId": product_id, "token": token},
            timeout=20
        )
        if res.status_code != 200:
            return {
                "最新成交价": 0,
                "最低挂售价": 0,
                "成交量": 0,
                "市场状态": f"获取失败（状态码：{res.status_code}）"
            }
        data = res.json().get("data", {})
        return {
            "最新成交价": data.get("lastSale", 0),
            "最低挂售价": data.get("lowestAsk", 0),
            "成交量": data.get("salesVolume", 0),
            "市场状态": "正常"
        }
    except Exception as e:
        return {
            "最新成交价": 0,
            "最低挂售价": 0,
            "成交量": 0,
            "市场状态": f"异常：{str(e)}"
        }

def get_historical_price(product_id: str) -> (pd.DataFrame, str):
    """获取历史价格+涨跌趋势"""
    token = get_token()
    try:
        res = requests.get(
            f"{BASE_URL}/product_size_historical_price",
            params={"productId": product_id, "size": "US 9", "token": token},
            timeout=25
        )
        if res.status_code != 200 or not res.json().get("data"):
            return pd.DataFrame(), "无历史数据"
        
        df = pd.DataFrame(res.json()["data"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        
        if len(df) < 2:
            return df, "数据不足（少于2条）"
        last = df.iloc[-1]["price"]
        prev = df.iloc[-2]["price"]
        change = last - prev
        change_pct = (change / prev) * 100 if prev != 0 else 0
        
        if change > 0:
            trend = f"📈 上涨 {change:.2f} ({change_pct:.1f}%)"
        elif change < 0:
            trend = f"📉 下跌 {abs(change):.2f} ({abs(change_pct):.1f}%)"
        else:
            trend = "➡️ 持平"
        
        return df, trend
    except Exception as e:
        return pd.DataFrame(), f"获取失败：{str(e)}"

def batch_query(style_id_list: List[str]) -> List[Dict]:
    """批量查询主逻辑"""
    results = []
    total = len(style_id_list)
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, style_id in enumerate(style_id_list):
        style_id = style_id.strip()
        if not style_id:
            continue
        status_text.text(f"查询中 {idx+1}/{total}：{style_id}")
        
        # 调用强化版搜索函数
        basic = search_product_enhanced(style_id)
        if basic["状态"] != "查询成功":
            results.append({
                **basic, 
                "最新成交价": 0, 
                "最低挂售价": 0, 
                "成交量": 0, 
                "涨跌趋势": "", 
                "历史数据": pd.DataFrame()
            })
            progress_bar.progress((idx+1)/total)
            time.sleep(QUERY_DELAY)
            continue
        
        # 获取销售信息
        market = get_market_info(basic["商品ID"])
        
        # 获取历史价格+涨跌
        hist_df, trend = get_historical_price(basic["商品ID"])
        
        # 合并结果
        results.append({**basic, **market, "涨跌趋势": trend, "历史数据": hist_df})
        
        progress_bar.progress((idx+1)/total)
        time.sleep(QUERY_DELAY)

    progress_bar.empty()
    status_text.text(f"✅ 完成！共查询 {len(results)} 个货号")
    return results

# -------------------------- Web界面 --------------------------
def main():
    st.set_page_config(page_title="StockX批量分析工具（终极版）", layout="wide")
    st.title("📊 StockX 批量货号分析智能体（终极调试版）")
    st.caption("支持：Style ID精准查询 | 自动强化搜索 | 全流程调试日志")

    # 侧边栏
    with st.sidebar:
        st.header("⚙️ 配置中心")
        token = get_token()
        st.text(f"Token状态：{'✅ 已配置' if token else '❌ 未配置'}")
        if st.button("🔍 验证Token"):
            if validate_token(token):
                st.success("✅ Token验证成功！")
            else:
                st.error("❌ Token无效/API不可达！")
        
        st.divider()
        st.warning("⚠️ 当前为调试版，会显示API原始返回数据，便于定位问题")

    # 货号输入
    st.divider()
    tab1, tab2 = st.tabs(["📝 手动输入", "📂 上传文件"])
    style_id_list = []

    with tab1:
        # 明确提示DD0587-002的输入方式
        gtin_text = st.text_area(
            "货号（Style ID/GTIN，每行一个）",
            placeholder="DD0587-002（AJ系列Style ID）\n195244229298（GTIN示例）"
        )
        if gtin_text:
            style_id_list = [x.strip() for x in gtin_text.split("\n") if x.strip()]

    with tab2:
        uploaded_file = st.file_uploader("上传TXT/CSV（第一列是货号）", type=["txt", "csv"])
        if uploaded_file:
            if uploaded_file.name.endswith(".txt"):
                style_id_list = [x.strip() for x in uploaded_file.read().decode("utf-8").split("\n") if x.strip()]
            else:
                df = pd.read_csv(uploaded_file)
                style_id_list = df.iloc[:,0].astype(str).tolist()
            st.success(f"✅ 读取到 {len(style_id_list)} 个货号")

    # 执行查询
    if st.button("🚀 开始批量分析", type="primary", disabled=not (token and style_id_list)):
        with st.spinner("正在分析数据（含调试日志），请稍候..."):
            st.session_state["results"] = batch_query(style_id_list)

    # 结果展示（新增调试信息列）
    if "results" in st.session_state and st.session_state["results"]:
        results = st.session_state["results"]
        
        # 1. 完整结果表格（含调试信息）
        st.divider()
        st.header("📋 查询结果（含调试日志）")
        # 处理历史数据列，只保留标识
        df_show = pd.DataFrame(results)
        df_show["历史数据"] = df_show["历史数据"].apply(lambda x: "有数据" if not x.empty else "无数据")
        st.dataframe(df_show, use_container_width=True)

        # 2. 调试信息展开（方便查看详细内容）
        st.divider()
        st.header("🔍 详细调试信息")
        for res in results:
            with st.expander(f"货号：{res['货号']} | 状态：{res['状态']}"):
                st.code(res["调试信息"], language="json")

        # 3. 价格走势对比
        st.divider()
        st.header("📈 价格走势对比")
        valid_results = [r for r in results if r["历史数据"] != "无数据"]
        if valid_results:
            combine_df = pd.DataFrame()
            for r in valid_results:
                # 重新获取完整历史数据（因展示时做了简化）
                hist_df, _ = get_historical_price(r["商品ID"])
                df = hist_df.copy()
                df["货号"] = r["货号"]
                combine_df = pd.concat([combine_df, df])
            
            fig = px.line(combine_df, x="date", y="price", color="货号", title="多货号价格走势对比")
            st.plotly_chart(fig, use_container_width=True)

            # 单个货号详情
            selected_gtin = st.selectbox("选择货号查看详情", [r["货号"] for r in valid_results])
            selected_r = next(r for r in valid_results if r["货号"] == selected_gtin)
            hist_df, trend = get_historical_price(selected_r["商品ID"])
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader(f"{selected_gtin} 历史走势")
                fig_single = px.line(hist_df, x="date", y="price", title=trend)
                st.plotly_chart(fig_single, use_container_width=True)
            with col2:
                st.subheader("核心销售数据")
                st.metric("最新成交价", f"${selected_r['最新成交价']:.2f}")
                st.metric("最低挂售价", f"${selected_r['最低挂售价']:.2f}")
                st.metric("成交量", selected_r["成交量"])
                st.metric("涨跌趋势", trend)
        else:
            st.warning("暂无有效历史价格数据（需先查询到商品）")

        # 4. 导出功能（剔除调试信息，保留核心数据）
        st.divider()
        st.header("💾 导出核心数据")
        df_export = pd.DataFrame(results)
        df_export = df_export.drop(columns=["调试信息", "历史数据"], errors="ignore")
        
        csv_buf = io.StringIO()
        df_export.to_csv(csv_buf, index=False, encoding="utf-8-sig")
        st.download_button("📥 导出CSV", csv_buf.getvalue(), f"StockX核心结果_{int(time.time())}.csv")
        
        excel_buf = io.BytesIO()
        df_export.to_excel(excel_buf, index=False, engine="openpyxl")
        st.download_button("📥 导出Excel", excel_buf.getvalue(), f"StockX核心结果_{int(time.time())}.xlsx")

if __name__ == "__main__":
    main()
