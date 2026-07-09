import streamlit as st
import pandas as pd
import time
import io
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException


def fetch_data(target_date, keyword):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    result_set = set()
    try:
        driver.get("http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search")
        wait = WebDriverWait(driver, 15)

        keyword_input = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='标题关键字']")))
        keyword_input.clear()
        keyword_input.send_keys(keyword)

        # 修改后：增加到 30 秒超时，确保服务器有足够时间加载
        search_btn = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., '查询')]"))
        )
        search_btn.click()
        time.sleep(3)

        is_finished = False
        while not is_finished:
            rows = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//table/tbody/tr")))
            for row in rows:
                cols = row.find_elements(By.TAG_NAME, "td")
                if len(cols) < 4:
                    continue
                stock_code = cols[0].text.strip()
                stock_name = cols[1].text.strip()
                announce_date = cols[-1].text.strip()[:10]

                if announce_date == target_date:
                    result_set.add((stock_code, stock_name))
                elif announce_date < target_date:
                    is_finished = True
                    break

            if is_finished:
                break

            try:
                next_btn = driver.find_element(By.XPATH, "//button[contains(@class, 'btn-next')]")
                if not next_btn.is_enabled():
                    break
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(2)
            except NoSuchElementException:
                break
    except Exception as e:
        st.error(f"运行异常: {e}")
    finally:
        driver.quit()

    if result_set:
        df = pd.DataFrame(list(result_set), columns=["代码", "简称"])
        df = df.sort_values(by="代码").reset_index(drop=True)
        return df
    return pd.DataFrame()


# 以下为前端界面逻辑
st.title("巨潮资讯公告定向检索系统")

# 采用两列布局放置输入控件
col1, col2 = st.columns(2)
with col1:
    target_date_input = st.date_input("选择查询日期")
with col2:
    keyword_input = st.text_input("输入标题关键字", value="向特定对象发行")

# 查询按钮触发逻辑
if st.button("开始查询"):
    date_str = target_date_input.strftime("%Y-%m-%d")

    # 显示加载动画
    with st.spinner(f"正在后台检索 {date_str} 的数据，请稍候..."):
        result_df = fetch_data(date_str, keyword_input)

        if not result_df.empty:
            st.success(f"查询完成，共找到 {len(result_df)} 条去重记录。")
            # 在网页上直接展示数据表格
            st.dataframe(result_df)

            # 将 DataFrame 写入内存中的字节流，用于生成下载链接
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                result_df.to_excel(writer, index=False)

            # 提供下载按钮
            st.download_button(
                label="下载 Excel 数据表",
                data=buffer.getvalue(),
                file_name=f"公告数据_{date_str}.xlsx",
                mime="application/vnd.ms-excel"
            )
        else:
            st.warning("未找到符合条件的数据。")