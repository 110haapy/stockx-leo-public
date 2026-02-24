=import streamlit as st
import requests
import pandas as pd
import time
import plotly.express as px
from typing import List, Dict
import io

# -------------------------- 配置区 --------------------------
BASE_URL = "https://api.spiderx.cc/api/stockx"
QUERY_DELAY = 2.5  # 延长延迟，避免API限流

# -------------------------- 核心函数 --------------------------
def get_token():
    """自动读取秘钥中的Token"""
    return st.secrets.get("STOCKX_TOKEN", "")

def get_auth():
    """返回你的账号邮箱作为auth参数"""
    return "lis460225@gmail.com"

def validate_token(token: str) -> bool:
    """验证Token是否有效"""
    try:
        res = requests.get(f"{BASE_URL}/ping", params={"token": token}, timeout=10)
        return res.status_code == 200
    except Exception as e:
        st.error(f"Token验证异常：{str(e)}")
        return False

def search_product_enhanced(style_id: str) -> Dict:
    """适配新版 /search_product 接口 + 多字段商品查找"""
    token = get_token()
    auth = get_auth()
    debug_info = {}
    
    try:
        # 新版接口：/search_product，参数为 keyword, auth, country, category
        search_res = requests.get(
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
        
        # 调试信息：保留完整的返回结构（加长字符数）
        debug_info["搜索接口状态码"] = search_res.status_code
        debug_info["搜索接口原始返回"] = search_res.text[:2000]  # 显示更多返回内容
        
        if search_res.status_code != 200:
            return {
                "货号": style_id,
                "状态": f"API请求失败（状态码：{search_res.status_code}）",
                "商品ID": "",
                "商品名称": "",
                "调试信息": str(debug_info)
            }
        
        search_data = search_res.json()
        data_root = search_data.get("data", {})
        debug_info["data根字段结构"] = str(list(data_root.keys()))  # 显示所有子字段
        
        # 核心优化：从多个可能的字段查找商品列表，覆盖所有常见返回格式
        products = []
        # 遍历所有可能的商品列表字段
        possible_fields = ["Featured", "Results", "Products", "products", "items", "list", "data"]
        for field in possible_fields:
            if field in data_root and isinstance(data_root[field], list) and len(data_root[field]) > 0:
                products = data_root[field]
                debug_info["有效商品列表字段"] = field
                break
        
        # 兜底：如果还是没找到，直接取data下的第一个列表型数据
        if not products and isinstance(data_root, dict):
            for k, v in data_root.items():
                if isinstance(v, list) and len(v) > 0:
                    products = v
                    debug_info["兜底匹配字段"] = k
                    break
        
        if not products:
            return {
                "货号": style_id,
                "状态": "未找到商品（所有列表均为空）",
                "商品ID": "",
                "商品名称": "",
                "调试信息": str(debug_info)
            }
        
        # 优先精确匹配Style ID（兼容大小写/空格）
        matched_product = None
        style_id_upper = style_id.strip().upper()
        for p in products:
            product_style_id = str(p.get("styleId", "")).strip().upper()
            if product_style_id == style_id_upper:
                matched_product = p
                debug_info["精确匹配成功"] = True
                break
        
        # 无精确匹配则取第一个结果
        if not matched_product:
            matched_product = products[0]
            debug_info["精确匹配失败"] = True
            st.info(f"未找到精确匹配的Style ID，取第一个搜索结果：{matched_product.get('title', '未知')}")

        return {
            "货号": style_id,
            "状态": "查询成功",
            "商品ID": matched_product.get("id"),
            "商品名称": matched_product.get("title", ""),
            "调试信息": str(debug_info)
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
    """获取销售信息（增强调试）"""
    token = get_token()
    auth = get_auth()
    debug_info = {}
    try:
        res = requests.get(
            f"{BASE_URL}/product_market_info",
            params={
                "token": token,
                "auth": auth,
                "productId": product_id
            },
            timeout=20
        )
        debug_info["market接口状态码"] = res.status_code
        debug_info["market接口原始返回"] = res.text[:1000]
        
        if res.status_code != 200:
            return {
                "最新成交价": 0,
                "最低挂售价": 0,
                "成交量": 0,
                "市场状态": f"获取失败（状态码：{res.status_code}）",
                "调试信息": str(debug_info)
            }
        data = res.json().get("data", {})
        return {
            "最新成交价": data.get("lastSale", 0),
            "最低挂售价": data.get("lowestAsk", 0),
            "成交量": data.get("salesVolume", 0),
            "市场状态": "正常",
            "调试信息": str(debug_info)
        }
    except Exception as e:
        return {
            "最新成交价": 0,
            "最低挂售价": 0,
            "成交量": 0,
            "市场状态": f"异常：{str(e)}",
            "调试信息": str(debug_info)
        }

def get_historical_price(product_id: str) -> (pd.DataFrame, str, dict):
    """获取历史价格+涨跌趋势（增强调试）"""
    token = get_token()
    auth = get_auth()
    debug_info = {}
    try:
        res = requests.get(
            f"{BASE_URL}/product_size_historical_price",
            params={
                "token": token,
                "auth": auth,
                "productId": product_id,
                "size": "US 9"
            },
            timeout=25
        )
        debug_info["history接口状态码"] = res.status_code
        debug_info["history接口原始返回"] = res.text[:1000]
        
        if res.status_code != 200 or not res.json().get("data"):
            return pd.DataFrame(), "无历史数据", debug_info
        
        df = pd.DataFrame(res.json()["data"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        
        if len(df) < 2:
            return df, "数据不足（少于2条）", debug_info
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
        
        return df, trend, debug_info
    except Exception as e:
        return pd.DataFrame(), f"获取失败：{str(e)}", debug_info

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
        
        basic = search_product_enhanced(style_id)
        if basic["状态"] != "查询成功":
            results.append({
                **basic, 
                "最新成交价": 0, 
                "最低挂售价": 0, 
                "成交量": 0, 
                "市场状态": "",
                "涨跌趋势": "", 
                "历史数据": pd.DataFrame()
            })
            progress_bar.progress((idx+1)/total)
            time.sleep(QUERY_DELAY)
            continue
        
        market = get_market_info(basic["商品ID"])
        hist_df, trend, hist_debug = get_historical_price(basic["商品ID"])
        
        # 合并所有调试信息
        market_debug = market.pop("调试信息", "{}")
        all_debug = {**eval(basic["调试信息"]), **eval(market_debug), **hist_debug}
        
        results.append({
            **basic, 
            **market, 
            "涨跌趋势": trend, 
            "历史数据": hist_df,
            "调试信息": str(all_debug)
        })
        
        progress_bar.progress((idx+1)/total)
        time.sleep(QUERY_DELAY)

    progress_bar.empty()
    status_text.text(f"✅ 完成！共查询 {len(results)} 个货号")
    return results

# -------------------------- Web界面 --------------------------
def main():
    st.set_page_config(page_title="StockX批量分析工具（最终调试版）", layout="wide")
    st.title("📊 StockX 批量货号分析智能体（最终调试版）")
    st.caption("适配新版API | 多字段商品匹配 | 全接口调试日志")

    with st.sidebar:
        st.header("⚙️ 配置中心")
        token = get_token()
        st.text(f"Token状态：{'✅ 已配置' if token else '❌ 未配置'}")
        st.text(f"Auth参数：{get_auth()}")
        if st.button("🔍 验证Token"):
            if validate_token(token):
                st.success("✅ Token验证成功！")
            else:
                st.error("❌ Token无效/API不可达！")
        
        st.divider()
        st.info("📌 支持货号类型：Style ID（如DD0587-002）、GTIN（数字码）")

    st.divider()
    tab1, tab2 = st.tabs(["📝 手动输入", "📂 上传文件"])
    style_id_list = []

    with tab1:
        gtin_text = st.text_area(
            "货号（Style ID/GTIN，每行一个）",
            placeholder="DD0587-002（AJ5 Wolf Grey 2026）\ncw2288-111（老款示例）"
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

    if st.button("🚀 开始批量分析", type="primary", disabled=not (get_token() and style_id_list)):
        with st.spinner("正在分析数据（含调试日志），请稍候..."):
            st.session_state["results"] = batch_query(style_id_list)

    if "results" in st.session_state and st.session_state["results"]:
        results = st.session_state["results"]
        
        # 1. 完整结果表格
        st.divider()
        st.header("📋 查询结果（含调试日志）")
        df_show = pd.DataFrame(results)
        df_show["历史数据"] = df_show["历史数据"].apply(lambda x: "有数据" if not x.empty else "无数据")
        st.dataframe(df_show, use_container_width=True)

        # 2. 详细调试信息（展开查看）
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
                hist_df, _ = get_historical_price(r["商品ID"])[:2]
                df = hist_df.copy()
                df["货号"] = r["货号"]
                combine_df = pd.concat([combine_df, df])
            
            fig = px.line(combine_df, x="date", y="price", color="货号", title="多货号价格走势对比")
            st.plotly_chart(fig, use_container_width=True)

            # 单个货号详情
            selected_gtin = st.selectbox("选择货号查看详情", [r["货号"] for r in valid_results])
            selected_r = next(r for r in valid_results if r["货号"] == selected_gtin)
            hist_df, trend = get_historical_price(selected_r["商品ID"])[:2]
            
            col1, col2 = st.columns(2)
            with col1:
                st.subheader(f"{selected_gtin} 历史走势")
                fig_single = px.line(hist_df, x="date", y="price", title=selected_r["涨跌趋势"])
                st.plotly_chart(fig_single, use_container_width=True)
            with col2:
                st.subheader("核心销售数据")
                st.metric("最新成交价", f"${selected_r['最新成交价']:.2f}")
                st.metric("最低挂售价", f"${selected_r['最低挂售价']:.2f}")
                st.metric("成交量", selected_r["成交量"])
                st.metric("涨跌趋势", selected_r["涨跌趋势"])
        else:
            st.warning("暂无有效历史价格数据（需先查询到商品）")

        # 4. 导出核心数据
        st.divider()
        st.header("💾 导出核心数据")
        df_export = pd.DataFrame(results)
        df_export = df_export.drop(columns=["调试信息", "历史数据"], errors="ignore")
        
        # CSV导出
        csv_buf = io.StringIO()
        df_export.to_csv(csv_buf, index=False, encoding="utf-8-sig")
        st.download_button("📥 导出CSV", csv_buf.getvalue(), f"StockX核心结果_{int(time.time())}.csv")
        
        # Excel导出
        excel_buf = io.BytesIO()
        df_export.to_excel(excel_buf, index=False, engine="openpyxl")
        st.download_button("📥 导出Excel", excel_buf.getvalue(), f"StockX核心结果_{int(time.time())}.xlsx")

if __name__ == "__main__":
    main()
