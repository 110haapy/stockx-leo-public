import streamlit as st
import requests
import pandas as pd
import time
import plotly.express as px
from typing import List, Dict
import io

# -------------------------- 配置区 --------------------------
BASE_URL = "https://api.spiderx.cc/api/stockx"
QUERY_DELAY = 2.5  # 避免API限流
TARGET_SIZE = "US 9"  # 目标查询尺码（可自行修改）

# -------------------------- 核心函数 --------------------------
def get_token():
    """自动读取秘钥中的Token"""
    return st.secrets.get("STOCKX_TOKEN", "")

def get_auth():
    """返回账号邮箱作为auth参数"""
    return "lis460225@gmail.com"

def validate_token(token: str) -> bool:
    """验证Token有效性"""
    try:
        res = requests.get(f"{BASE_URL}/ping", params={"token": token}, timeout=10)
        return res.status_code == 200
    except Exception as e:
        st.error(f"Token验证异常：{str(e)}")
        return False

def search_product_enhanced(style_id: str) -> Dict:
    """步骤1：搜索商品，获取productId"""
    token, auth = get_token(), get_auth()
    debug_info = {"步骤": "搜索商品", "货号": style_id}
    
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
            return {
                "货号": style_id,
                "状态": f"搜索失败（状态码：{res.status_code}）",
                "商品ID": "",
                "商品名称": "",
                "调试信息": str(debug_info)
            }
        
        search_data = res.json()
        data_root = search_data.get("data", {})
        
        # 多字段查找商品列表
        products = (
            data_root.get("Featured", [])
            or data_root.get("Results", [])
            or data_root.get("Products", [])
            or []
        )
        
        if not products:
            return {
                "货号": style_id,
                "状态": "未找到商品",
                "商品ID": "",
                "商品名称": "",
                "调试信息": str(debug_info)
            }
        
        # 优先精确匹配Style ID
        matched_product = None
        style_id_upper = style_id.strip().upper()
        for p in products:
            product_style_id = str(p.get("styleId", "")).strip().upper()
            if product_style_id == style_id_upper:
                matched_product = p
                break
        
        if not matched_product:
            matched_product = products[0]
            debug_info["匹配说明"] = "未精确匹配，取第一个搜索结果"
        
        return {
            "货号": style_id,
            "状态": "查询成功",
            "商品ID": matched_product.get("id", ""),
            "商品名称": matched_product.get("title", ""),
            "调试信息": str(debug_info)
        }
    except Exception as e:
        return {
            "货号": style_id,
            "状态": f"执行异常：{str(e)}",
            "商品ID": "",
            "商品名称": "",
            "调试信息": str(debug_info)
        }

def get_product_detail(product_id: str) -> Dict:
    """步骤2：获取商品详情，提取目标尺码的product_uuid（核心）"""
    token, auth = get_token(), get_auth()
    debug_info = {"步骤": "获取商品详情", "商品ID": product_id}
    
    if not product_id:
        return {
            "uuid": "",
            "尺码信息": "商品ID为空",
            "调试信息": str(debug_info)
        }
    
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
            return {
                "uuid": "",
                "尺码信息": f"接口调用失败（状态码：{res.status_code}）",
                "调试信息": str(debug_info)
            }
        
        data = res.json().get("data", {})
        sizes = data.get("sizes", [])  # 官方文档核心字段：尺码列表
        
        # 查找目标尺码的uuid
        target_uuid = ""
        for size in sizes:
            if size.get("size") == TARGET_SIZE:
                target_uuid = size.get("uuid", "")
                break
        
        size_info = f"找到{TARGET_SIZE}尺码UUID: {target_uuid[:10]}..." if target_uuid else f"未找到{TARGET_SIZE}尺码"
        return {
            "uuid": target_uuid,
            "尺码信息": size_info,
            "调试信息": str(debug_info)
        }
    except Exception as e:
        return {
            "uuid": "",
            "尺码信息": f"执行异常：{str(e)}",
            "调试信息": str(debug_info)
        }

def get_market_data(uuid: str) -> Dict:
    """步骤3：用uuid查询真实市场数据（官方推荐接口）"""
    token, auth = get_token(), get_auth()
    debug_info = {"步骤": "查询市场数据", "UUID": uuid[:10] + "..." if uuid else "空"}
    
    if not uuid:
        return {
            "最新成交价": 0,
            "最低挂售价": 0,
            "成交量": 0,
            "市场状态": "无有效UUID",
            "调试信息": str(debug_info)
        }
    
    try:
        # 官方推荐接口：product_size_activity_new
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
            return {
                "最新成交价": 0,
                "最低挂售价": 0,
                "成交量": 0,
                "市场状态": f"接口调用失败（状态码：{res.status_code}）",
                "调试信息": str(debug_info)
            }
        
        data = res.json().get("data", {})
        # 解析官方文档标准字段
        last_sale = data.get("lastSale", {}).get("price", 0)
        lowest_ask = data.get("lowestAsk", {}).get("price", 0)
        sales_volume = len(data.get("sales", []))  # 成交记录数=成交量
        
        return {
            "最新成交价": last_sale,
            "最低挂售价": lowest_ask,
            "成交量": sales_volume,
            "市场状态": "正常",
            "调试信息": str(debug_info)
        }
    except Exception as e:
        return {
            "最新成交价": 0,
            "最低挂售价": 0,
            "成交量": 0,
            "市场状态": f"执行异常：{str(e)}",
            "调试信息": str(debug_info)
        }

def batch_query(style_id_list: List[str]) -> List[Dict]:
    """批量执行完整数据链路"""
    results = []
    total = len(style_id_list)
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, style_id in enumerate(style_id_list):
        style_id = style_id.strip()
        if not style_id:
            continue
        
        status_text.text(f"处理中 {idx+1}/{total}：{style_id}")
        
        # 步骤1：搜索商品
        step1 = search_product_enhanced(style_id)
        
        if step1["状态"] != "查询成功":
            # 搜索失败，补充默认字段避免KeyError
            results.append({
                **step1,
                "尺码信息": "",
                "最新成交价": 0,
                "最低挂售价": 0,
                "成交量": 0,
                "市场状态": "搜索失败"
            })
            progress_bar.progress((idx+1)/total)
            time.sleep(QUERY_DELAY)
            continue
        
        # 步骤2：获取尺码UUID
        step2 = get_product_detail(step1["商品ID"])
        
        # 步骤3：查询市场数据
        step3 = get_market_data(step2["uuid"])
        
        # 合并所有调试信息
        combined_debug = (
            f"【1】搜索商品：{step1['调试信息']}\n"
            f"【2】获取详情：{step2['调试信息']}\n"
            f"【3】查询市场：{step3['调试信息']}"
        )
        
        # 组装最终结果（确保所有字段都存在）
        results.append({
            "货号": style_id,
            "状态": step1["状态"],
            "商品ID": step1["商品ID"],
            "商品名称": step1["商品名称"],
            "尺码信息": step2["尺码信息"],
            "最新成交价": step3["最新成交价"],
            "最低挂售价": step3["最低挂售价"],
            "成交量": step3["成交量"],
            "市场状态": step3["市场状态"],
            "调试信息": combined_debug
        })
        
        progress_bar.progress((idx+1)/total)
        time.sleep(QUERY_DELAY)

    progress_bar.empty()
    status_text.text(f"✅ 完成！共处理 {len(results)} 个货号")
    return results

# -------------------------- Web界面（修复KeyError） --------------------------
def main():
    st.set_page_config(page_title="StockX批量分析工具（最终稳定版）", layout="wide")
    st.title("📊 StockX 批量货号分析智能体（最终稳定版）")
    st.caption(f"适配官方接口 | 目标尺码：{TARGET_SIZE} | 防KeyError报错")

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
        st.info(f"📌 目标查询尺码：{TARGET_SIZE}\n如需修改，可在代码配置区调整")
        st.warning("⚠️ 新款商品可能无成交数据，显示0为正常现象")

    st.divider()
    # 货号输入区域
    tab1, tab2 = st.tabs(["📝 手动输入", "📂 上传文件"])
    style_id_list = []

    with tab1:
        gtin_text = st.text_area(
            "货号（Style ID/GTIN，每行一个）",
            placeholder="cw2288-111（Air Force 1 白）\nDD0587-002（AJ5 Wolf Grey 2026）"
        )
        if gtin_text:
            style_id_list = [x.strip() for x in gtin_text.split("\n") if x.strip()]

    with tab2:
        uploaded_file = st.file_uploader("上传TXT/CSV（第一列是货号）", type=["txt", "csv"])
        if uploaded_file:
            try:
                if uploaded_file.name.endswith(".txt"):
                    style_id_list = [x.strip() for x in uploaded_file.read().decode("utf-8").split("\n") if x.strip()]
                else:
                    df_upload = pd.read_csv(uploaded_file)
                    style_id_list = df_upload.iloc[:,0].astype(str).tolist()
                st.success(f"✅ 读取到 {len(style_id_list)} 个货号")
            except Exception as e:
                st.error(f"文件读取失败：{str(e)}")

    # 批量分析按钮
    if st.button("🚀 开始批量分析", type="primary", disabled=not (token and style_id_list)):
        with st.spinner("正在执行完整数据链路，请稍候..."):
            st.session_state["results"] = batch_query(style_id_list)

    # 结果展示区域
    if "results" in st.session_state and st.session_state["results"]:
        results = st.session_state["results"]
        df_results = pd.DataFrame(results)
        
        # 1. 核心结果表格（防KeyError：只展示存在的列）
        st.divider()
        st.header("📋 核心查询结果")
        desired_columns = ["货号", "商品名称", "尺码信息", "最新成交价", "最低挂售价", "成交量", "市场状态"]
        display_columns = [col for col in desired_columns if col in df_results.columns]
        
        if display_columns:
            st.dataframe(df_results[display_columns], use_container_width=True)
        else:
            st.warning("暂无可展示的核心数据，请查看下方调试日志")

        # 2. 全链路调试日志
        st.divider()
        st.header("🔍 全链路调试日志")
        for idx, res in enumerate(results):
            with st.expander(f"[{idx+1}] 货号：{res.get('货号', '未知')} | 状态：{res.get('市场状态', '未知')}"):
                st.code(res.get("调试信息", "无调试信息"), language="json")

        # 3. 数据导出功能
        st.divider()
        st.header("💾 导出数据")
        
        # 清理导出数据（移除大文本调试信息）
        df_export = df_results.copy()
        if "调试信息" in df_export.columns:
            df_export = df_export.drop(columns=["调试信息"])
        
        # CSV导出
        csv_buffer = io.StringIO()
        df_export.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 导出CSV文件",
            data=csv_buffer.getvalue(),
            file_name=f"StockX批量查询结果_{int(time.time())}.csv",
            mime="text/csv"
        )
        
        # Excel导出
        try:
            excel_buffer = io.BytesIO()
            df_export.to_excel(excel_buffer, index=False, engine="openpyxl")
            st.download_button(
                label="📥 导出Excel文件",
                data=excel_buffer.getvalue(),
                file_name=f"StockX批量查询结果_{int(time.time())}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.warning(f"Excel导出失败：{str(e)}，建议使用CSV导出")

if __name__ == "__main__":
    main()
