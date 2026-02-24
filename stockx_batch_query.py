import streamlit as st
import requests
import pandas as pd
import time
import plotly.express as px
from typing import List, Dict
import io

# -------------------------- 配置区 --------------------------
BASE_URL = "https://api.spiderx.cc/api/stockx"
QUERY_DELAY = 2.0  # 延迟2秒，避免限流

# -------------------------- 核心函数 --------------------------
def get_token():
    """自动读取秘钥中的Token"""
    return st.secrets.get("STOCKX_TOKEN", "")

def validate_token(token: str) -> bool:
    """验证Token是否有效"""
    try:
        res = requests.get(f"{BASE_URL}/ping", params={"token": token}, timeout=10)
        return res.status_code == 200
    except Exception:
        return False

# ========== 关键修改：适配Style ID（如DD0587-002）查询 ==========
def search_product_by_style_id(style_id: str) -> Dict:
    """按Style ID/货号搜索商品（兼容数字GTIN和字符Style ID）"""
    token = get_token()
    try:
        # 改用search接口，支持Style ID关键词搜索
        search_res = requests.get(
            f"{BASE_URL}/search",
            params={"q": style_id, "token": token},
            timeout=15
        )
        if search_res.status_code != 200 or not search_res.json().get("data"):
            return {"货号": style_id, "状态": "未找到商品", "商品ID": "", "商品名称": ""}
        
        # 优先匹配Style ID完全一致的商品，提升精准度
        products = search_res.json()["data"]
        matched_product = None
        for p in products:
            if p.get("styleId", "").strip().upper() == style_id.strip().upper():
                matched_product = p
                break
        # 无精确匹配时取第一个结果
        if not matched_product:
            matched_product = products[0]

        return {
            "货号": style_id,
            "状态": "查询成功",
            "商品ID": matched_product.get("id"),
            "商品名称": matched_product.get("title", "")
        }
    except Exception as e:
        return {"货号": style_id, "状态": f"异常：{str(e)}", "商品ID": "", "商品名称": ""}

def get_market_info(product_id: str) -> Dict:
    """获取销售信息（成交价/挂售价/销量）"""
    token = get_token()
    try:
        res = requests.get(
            f"{BASE_URL}/product_market_info",
            params={"productId": product_id, "token": token},
            timeout=15
        )
        if res.status_code != 200:
            return {"最新成交价": 0, "最低挂售价": 0, "成交量": 0, "市场状态": "获取失败"}
        data = res.json().get("data", {})
        return {
            "最新成交价": data.get("lastSale", 0),
            "最低挂售价": data.get("lowestAsk", 0),
            "成交量": data.get("salesVolume", 0),
            "市场状态": "正常"
        }
    except Exception as e:
        return {"最新成交价": 0, "最低挂售价": 0, "成交量": 0, "市场状态": f"异常：{str(e)}"}

def get_historical_price(product_id: str) -> (pd.DataFrame, str):
    """获取历史价格+涨跌趋势"""
    token = get_token()
    try:
        res = requests.get(
            f"{BASE_URL}/product_size_historical_price",
            params={"productId": product_id, "size": "US 9", "token": token},
            timeout=20
        )
        if res.status_code != 200 or not res.json().get("data"):
            return pd.DataFrame(), "无历史数据"
        
        df = pd.DataFrame(res.json()["data"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        
        # 计算涨跌
        if len(df) < 2:
            return df, "数据不足"
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

def batch_query(gtin_list: List[str]) -> List[Dict]:
    """批量查询主逻辑"""
    results = []
    total = len(gtin_list)
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, gtin in enumerate(gtin_list):
        gtin = gtin.strip()
        if not gtin:
            continue
        status_text.text(f"查询中 {idx+1}/{total}：{gtin}")
        
        # ========== 关键修改：调用新的Style ID查询函数 ==========
        basic = search_product_by_style_id(gtin)
        if basic["状态"] != "查询成功":
            results.append({**basic, "最新成交价": 0, "最低挂售价": 0, "成交量": 0, "涨跌趋势": "", "历史数据": pd.DataFrame()})
            progress_bar.progress((idx+1)/total)
            time.sleep(QUERY_DELAY)
            continue
        
        # 2. 销售信息
        market = get_market_info(basic["商品ID"])
        
        # 3. 历史价格+涨跌
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
    st.set_page_config(page_title="StockX批量分析工具", layout="wide")
    st.title("📊 StockX 批量货号分析智能体（公开版）")
    st.caption("支持：Style ID/GTIN查询、销售信息、历史走势、多货号对比、涨跌提醒")

    # 侧边栏
    with st.sidebar:
        st.header("⚙️ 配置")
        # 自动加载Token，无需手动输入
        token = get_token()
        st.text(f"Token状态：{'✅ 已配置' if token else '❌ 未配置'}")
        if st.button("🔍 验证Token"):
            if validate_token(token):
                st.success("✅ Token有效！")
            else:
                st.error("❌ Token无效！")
        
        st.divider()
        st.info("📌 使用说明：\n1. 输入货号（Style ID/GTIN，每行一个）\n2. 点击查询\n3. 查看结果/导出数据")

    # 货号输入
    st.divider()
    tab1, tab2 = st.tabs(["📝 手动输入", "📂 上传文件"])
    gtin_list = []

    with tab1:
        gtin_text = st.text_area("货号（Style ID/GTIN，每行一个）", placeholder="DD0587-002\n195244229298")
        if gtin_text:
            gtin_list = [x.strip() for x in gtin_text.split("\n") if x.strip()]

    with tab2:
        uploaded_file = st.file_uploader("上传TXT/CSV（第一列是货号）", type=["txt", "csv"])
        if uploaded_file:
            if uploaded_file.name.endswith(".txt"):
                gtin_list = [x.strip() for x in uploaded_file.read().decode("utf-8").split("\n") if x.strip()]
            else:
                df = pd.read_csv(uploaded_file)
                gtin_list = df.iloc[:,0].astype(str).tolist()
            st.success(f"✅ 读取到 {len(gtin_list)} 个货号")

    # 执行查询
    if st.button("🚀 开始批量分析", type="primary", disabled=not (token and gtin_list)):
        with st.spinner("分析中..."):
            st.session_state["results"] = batch_query(gtin_list)

    # 结果展示
    if "results" in st.session_state and st.session_state["results"]:
        results = st.session_state["results"]
        
        # 1. 数据表格
        st.divider()
        st.header("📋 查询结果")
        df_show = pd.DataFrame(results).drop(columns=["商品ID", "历史数据"], errors="ignore")
        st.dataframe(df_show, use_container_width=True)

        # 2. 价格走势
        st.divider()
        st.header("📈 价格走势对比")
        valid_results = [r for r in results if not r["历史数据"].empty]
        if valid_results:
            # 多货号对比图
            combine_df = pd.DataFrame()
            for r in valid_results:
                df = r["历史数据"].copy()
                df["货号"] = r["货号"]
                combine_df = pd.concat([combine_df, df])
            
            fig = px.line(combine_df, x="date", y="price", color="货号", title="多货号价格走势")
            st.plotly_chart(fig, use_container_width=True)

            # 单个货号详情
            selected_gtin = st.selectbox("选择货号看详情", [r["货号"] for r in valid_results])
            selected_r = next(r for r in valid_results if r["货号"] == selected_gtin)
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader(f"{selected_gtin} 历史走势")
                fig_single = px.line(selected_r["历史数据"], x="date", y="price", title=selected_r["涨跌趋势"])
                st.plotly_chart(fig_single, use_container_width=True)
            with col2:
                st.subheader("核心数据")
                st.metric("最新成交价", f"${selected_r['最新成交价']:.2f}")
                st.metric("最低挂售价", f"${selected_r['最低挂售价']:.2f}")
                st.metric("成交量", selected_r["成交量"])
                st.metric("涨跌趋势", selected_r["涨跌趋势"])
        else:
            st.warning("暂无历史价格数据")

        # 3. 导出
        st.divider()
        st.header("💾 导出数据")
        df_export = pd.DataFrame(results).drop(columns=["历史数据"], errors="ignore")
        
        # CSV导出
        csv_buf = io.StringIO()
        df_export.to_csv(csv_buf, index=False, encoding="utf-8-sig")
        st.download_button("📥 导出CSV", csv_buf.getvalue(), f"StockX结果_{int(time.time())}.csv")
        
        # Excel导出
        excel_buf = io.BytesIO()
        df_export.to_excel(excel_buf, index=False, engine="openpyxl")
        st.download_button("📥 导出Excel", excel_buf.getvalue(), f"StockX结果_{int(time.time())}.xlsx")

if __name__ == "__main__":
    main()
