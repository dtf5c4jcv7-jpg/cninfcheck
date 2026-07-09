import streamlit as st
import pandas as pd
import requests
import time
import io
import re
from datetime import datetime

# ========== 配置 ==========
API_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "http://www.cninfo.com.cn",
}
PAGE_SIZE = 30  # 每页条数


def ms_timestamp_to_date(ts_ms: int) -> str:
    """将毫秒时间戳转为 YYYY-MM-DD 字符串"""
    try:
        return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d")
    except (ValueError, OSError):
        return ""


def strip_html_tags(text: str) -> str:
    """去除 HTML 标签（如搜索高亮的 <em> 标记）"""
    return re.sub(r"<[^>]+>", "", text)


def fetch_data(target_date: str, keyword: str) -> pd.DataFrame:
    """
    从巨潮资讯网 API 抓取指定日期和关键字的公告数据

    Args:
        target_date: 日期字符串 "YYYY-MM-DD"
        keyword:    标题关键字

    Returns:
        包含代码、简称、公告标题、公告日期、公告链接的 DataFrame
    """
    all_records = []
    page_num = 1

    with st.status(f"正在查询 {target_date} 包含「{keyword}」的公告...", expanded=True) as status:
        while True:
            payload = {
                "pageNum": page_num,
                "pageSize": PAGE_SIZE,
                "column": "szse",          # 深沪京
                "tabName": "fulltext",      # 公告全文
                "plate": "sz;sh;bj",        # 深市;沪市;北交所
                "stock": "",
                "searchkey": keyword,
                "secid": "",
                "category": "",
                "trade": "",
                "seDate": f"{target_date}~{target_date}",
                "sortName": "",
                "sortType": "desc",
                "isHLtitle": "true",
            }

            try:
                resp = requests.post(API_URL, data=payload, headers=HEADERS, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except requests.exceptions.RequestException as e:
                st.error(f"第 {page_num} 页请求失败: {e}")
                break
            except ValueError as e:
                st.error(f"JSON 解析失败: {e}")
                break

            announcements = data.get("announcements", [])
            total = data.get("totalAnnouncement", 0)

            if not announcements:
                break

            for item in announcements:
                sec_code = item.get("secCode", "")
                sec_name = strip_html_tags(item.get("secName", ""))
                title = strip_html_tags(item.get("announcementTitle", ""))
                ts_ms = item.get("announcementTime", 0)
                announce_date = ms_timestamp_to_date(ts_ms)
                announce_id = item.get("announcementId", "")
                adjunct_url = item.get("adjunctUrl", "")

                # 构建公告详情页链接
                detail_url = (
                    f"http://www.cninfo.com.cn/new/disclosure/detail"
                    f"?stockCode={sec_code}"
                    f"&announcementId={announce_id}"
                    f"&announcementTime={announce_date}"
                )

                all_records.append({
                    "代码": sec_code,
                    "简称": sec_name,
                    "公告标题": title,
                    "公告日期": announce_date,
                    "公告ID": announce_id,
                    "公告链接": detail_url,
                })

            st.write(f"已获取第 {page_num} 页，累计 {len(all_records)} 条 / 共 {total} 条")

            # 判断是否还有下一页
            if page_num * PAGE_SIZE >= total:
                break
            page_num += 1
            time.sleep(0.5)  # 礼貌间隔，避免请求过快

        if all_records:
            status.update(
                label=f"查询完成，共获取 {len(all_records)} 条公告",
                state="complete",
            )
        else:
            status.update(label="未找到匹配的公告", state="complete")

    if all_records:
        df = pd.DataFrame(all_records)
        df = df.sort_values(by=["代码", "公告日期"]).reset_index(drop=True)
        return df
    return pd.DataFrame()


# ========== Streamlit 前端界面 ==========
st.set_page_config(
    page_title="巨潮资讯公告检索",
    page_icon="📊",
    layout="wide",
)
st.title("📊 巨潮资讯网公告定向检索系统")
st.caption("数据来源：巨潮资讯网 (cninfo.com.cn) · 中国证监会指定信息披露网站")

# 输入区域
col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    target_date_input = st.date_input("📅 选择查询日期")
with col2:
    keyword_input = st.text_input(
        "🔍 输入标题关键字",
        value="向特定对象发行",
        placeholder="例如：向特定对象发行、重大资产重组、年报",
    )
with col3:
    st.markdown("")  # 占位对齐
    st.markdown("")
    search_clicked = st.button("🚀 开始查询", type="primary", use_container_width=True)

# 快捷关键字
st.caption("常用关键字：")
quick_keywords = st.pills(
    "快捷关键字",
    options=[
        "向特定对象发行",
        "重大资产重组",
        "年报",
        "半年报",
        "权益分派",
        "股权激励",
        "减持",
        "增持",
        "可转债",
    ],
    default="向特定对象发行",
    label_visibility="collapsed",
)
# 点击快捷关键字时更新输入框
if quick_keywords and quick_keywords != keyword_input:
    keyword_input = quick_keywords

# 查询逻辑
if search_clicked:
    date_str = target_date_input.strftime("%Y-%m-%d")
    kw = keyword_input.strip() if isinstance(keyword_input, str) else quick_keywords

    if not kw:
        st.warning("⚠️ 请输入关键字")
    else:
        result_df = fetch_data(date_str, kw)

        if not result_df.empty:
            st.success(f"✅ 查询完成，共找到 **{len(result_df)}** 条去重记录")
            st.dataframe(
                result_df,
                use_container_width=True,
                column_config={
                    "代码": st.column_config.TextColumn("代码", width="small"),
                    "简称": st.column_config.TextColumn("简称", width="small"),
                    "公告标题": st.column_config.TextColumn("公告标题", width="large"),
                    "公告日期": st.column_config.TextColumn("公告日期", width="small"),
                    "公告链接": st.column_config.LinkColumn("公告链接", width="small"),
                },
                hide_index=True,
            )

            # Excel 下载
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                result_df.to_excel(writer, index=False, sheet_name="公告数据")
            st.download_button(
                label="📥 下载 Excel 数据表",
                data=buffer.getvalue(),
                file_name=f"公告数据_{date_str}_{kw}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.warning(f"未找到 {date_str} 包含「**{kw}**」的公告数据")
            st.info("💡 提示：请检查日期是否正确，或尝试更换关键字")
