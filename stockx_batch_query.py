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
        
        # 1. 结果表格：只展示实际存在的列，避免 KeyError
        st.divider()
        st.header("📋 核心结果")
        # 只保留 DataFrame 中实际存在的列
        desired_cols = ["货号", "商品名称", "尺码信息", "最新成交价", "最低挂售价", "成交量", "市场状态"]
        show_cols = [col for col in desired_cols if col in df.columns]
        if show_cols:
            st.dataframe(df[show_cols], use_container_width=True)
        else:
            st.warning("结果中无有效列可展示，可查看下方调试日志")

        # 2. 详细调试（展开查看）
        st.divider()
        st.header("🔍 全链路调试日志")
        for _, row in df.iterrows():
            with st.expander(f"货号：{row.get('货号', '未知')} | 状态：{row.get('市场状态', '未知')}"):
                st.code(row.get("调试信息", "无调试信息"), language="json")

        # 3. 导出
        st.divider()
        st.header("💾 导出数据")
        csv_buf = io.StringIO()
        df.to_csv(csv_buf, index=False, encoding="utf-8-sig")
        st.download_button("📥 导出 CSV", csv_buf.getvalue(), f"StockX结果_{int(time.time())}.csv")

if __name__ == "__main__":
    main()
