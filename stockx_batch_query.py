import streamlit as st
import requests
import pandas as pd
import time
import io

# -------------------------- 配置区 --------------------------
BASE_URL = "https://api.spiderx.cc/api/stockx"
QUERY_DELAY = 2.5
TARGET_SIZE = "US 9"

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
        products = data_root.get("Featured", []) or data_root.get("Results", []) or []
        
        if not products:
            return {
                "货号": style_id,
                "状态": "未找到商品",
                "商品ID": "",
                "商品名称": "",
                "调试信息": str(debug_info)
            }
        
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
                "product_id": product_id,
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
        size_variants = data.get("sizeVariants", [])
        
        target_uuid = ""
        for variant in size_variants:
            if variant.get("size") == TARGET_SIZE:
                target_uuid = variant.get("uuid", "")
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
        res = requests.get(
            f"{BASE_URL}/product_size_activity_new",
            params={
                "token": token,
                "auth": auth,
                "productUuid": uuid,
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
        last_sale = data.get("lastSale", {}).get("price", 0)
        lowest_ask = data.get("lowestAsk", {}).get("price", 0)
        sales_volume = len(data.get("sales", []))
        
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
    results = []
    total = len(style_id_list)
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, style_id in enumerate(style_id_list):
        style_id = style_id.strip()
        if not style_id:
            continue
        
        status_text.text(f"处理中 {idx+1}/{total}：{style_id}")
        
        step1 = search_product_enhanced(style_id)
        
        if step1["状态"] != "查询成功":
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
        
        step2 = get_product_detail(step1["商品ID"])
        step3 = get_market_data(step2["uuid"])
        
        combined_debug = (
            f"【1】搜索商品：{step1['调试信息']}\n"
            f"【2】获取详情：{step2['调试信息']}\n"
            f"【3】查询市场：{step3['调试信息']}"
        )
        
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

# -------------------------- Web界面 --------------------------
def main():
    st.set_page_config(page_title="StockX批量分析工具（最终修正版）", layout="wide")
    st.title("📊 StockX 批量货号分析智能体（最终修正版）")
    st.caption(f"严格遵循官方文档 | 目标尺码：{TARGET_SIZE}")

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
        st.info(f"📌 目标查询尺码：{TARGET_SIZE}")
        st.warning("⚠️ 新款商品可能无成交数据，显示0为正常现象")

    st.divider()
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

    if st.button("🚀 开始批量分析", type="primary", disabled=not (token and style_id_list)):
        with st.spinner("正在执行完整数据链路，请稍候..."):
            st.session_state["results"] = batch_query(style_id_list)

    if "results" in st.session_state and st.session_state["results"]:
        results = st.session_state["results"]
        df_results = pd.DataFrame(results)
        
        st.divider()
        st.header("📋 核心查询结果")
        desired_columns = ["货号", "商品名称", "尺码信息", "最新成交价", "最低挂售价", "成交量", "市场状态"]
        display_columns = [col for col in desired_columns if col in df_results.columns]
        
        if display_columns:
            st.dataframe(df_results[display_columns], use_container_width=True)
        else:
            st.warning("暂无可展示的核心数据，请查看下方调试日志")

        st.divider()
        st.header("🔍 全链路调试日志")
        for idx, res in enumerate(results):
            with st.expander(f"[{idx+1}] 货号：{res.get('货号', '未知')} | 状态：{res.get('市场状态', '未知')}"):
                st.code(res.get("调试信息", "无调试信息"), language="json")

        st.divider()
        st.header("💾 导出数据")
        df_export = df_results.copy()
        if "调试信息" in df_export.columns:
            df_export = df_export.drop(columns=["调试信息"])
        
        csv_buffer = io.StringIO()
        df_export.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
        st.download_button(
            label="📥 导出CSV文件",
            data=csv_buffer.getvalue(),
            file_name=f"StockX批量查询结果_{int(time.time())}.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    main()
