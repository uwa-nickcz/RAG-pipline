# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/29 13:47
# @File     : generate.py
# @contact  ： ***
from docx import Document
from docx.shared import Inches
import markdown
from bs4 import BeautifulSoup
import tempfile
import os
import re
import json


# 假设 generation 函数和 config, GENERATE_REPORT_PROMPT 是正确导入的
from llm.qwen_vllm import generation
from config import config
from prompt import GENERATE_REPORT_PROMPT

from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import numpy as np
import matplotlib

# 在某些服务器环境（如无GUI的Linux），需要设置后端为 'Agg' 以避免Tkinter等GUI相关的错误
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm  # 导入字体管理模块
import time


class ReportGenerator:
    def __init__(self):
        self.prompt = GENERATE_REPORT_PROMPT
        # --- 在初始化时设置中文字体 ---
        self._set_chinese_font()

    def _set_chinese_font(self):
        """尝试设置支持中文的字体"""
        # 1. 获取系统中所有可用字体的名称
        available_fonts = set(f.name for f in fm.fontManager.ttflist)
        # print("可用字体:", available_fonts) # 可用于调试，查看有哪些字体

        # 2. 定义一系列常用的中文字体名称（按优先级排序）
        chinese_fonts = [
            'SimHei',  # Windows 黑体
            'Microsoft YaHei',  # Windows 雅黑
            'STHeiti',  # macOS/iOS 华文黑体
            'Songti SC',  # macOS 宋体
            'PingFang SC',  # macOS 苹方
            'Noto Sans CJK SC',  # Google Noto 字体 (跨平台)
            'WenQuanYi Micro Hei',  # Linux 文泉驿微米黑
            'FandolSong',  # Linux Fandol 宋体
            'DejaVu Sans',  # 通用字体，有时包含中文子集
        ]

        # 3. 遍历列表，找到第一个可用的字体
        font_found = False
        for font_name in chinese_fonts:
            if font_name in available_fonts:
                # 4. 设置全局字体
                plt.rcParams['font.sans-serif'] = [font_name]
                # 5. 解决负号 '-' 显示为方块的问题
                plt.rcParams['axes.unicode_minus'] = False
                print(f"已设置中文字体为: {font_name}")
                font_found = True
                break

        if not font_found:
            print("警告: 未找到可用的中文字体。可能会出现乱码。")
            # 可以尝试列出一些可用字体供调试
            # print("部分可用字体:", list(available_fonts)[:10])

    def build_llm_prompt(self, dataframe: pd.DataFrame, user_request) -> str:
        """
        构建给大模型的prompt，明确要求返回结构化信息，支持 group_by
        """
        columns_info = []
        for col in dataframe.columns:
            dtype = str(dataframe[col].dtype)
            if dtype == 'object':
                unique_count = dataframe[col].nunique()
                sample_values = dataframe[col].dropna().unique().tolist()[:3]
                columns_info.append({
                    "column_name": col,
                    "data_type": dtype,
                    "unique_count": unique_count,
                    "sample_values": sample_values
                })
            else:
                sample_values = dataframe[col].head(3).tolist()
                columns_info.append({
                    "column_name": col,
                    "data_type": dtype,
                    "sample_values": sample_values
                })

        numeric_cols = dataframe.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = dataframe.select_dtypes(include=['object', 'category']).columns.tolist()
        datetime_cols = dataframe.select_dtypes(include=['datetime64[ns]', 'datetime']).columns.tolist()

        data_summary = {
            "total_rows": len(dataframe),
            "total_columns": len(dataframe.columns),
            "numeric_columns": numeric_cols,
            "categorical_columns": categorical_cols,
            "datetime_columns": datetime_cols
        }

        # 修改提示词，加入 group_by
        prompt = f"""
你是一个数据可视化专家。请根据用户的需求和提供的数据信息，推荐最合适的图表类型和配置。

数据信息：
- 数据概览：{json.dumps(data_summary, ensure_ascii=False, indent=2)}
- 列信息：{json.dumps(columns_info, ensure_ascii=False, indent=2)}

用户需求：{user_request if user_request else "请根据数据特征推荐合适的图表"}

请严格按照以下 JSON 格式返回你的建议，不要包含其他解释性文字：

{{
    "chart_type": "line", // 图表类型 (bar, line, pie, scatter 之一)
    "x_axis": "Date", // X轴使用的列名 (字符串，必须存在)
    "y_axis": "Sales", // Y轴使用的列名 (字符串，必须存在)
    "group_by": "Category", // 用于分组绘制多条线的列名 (字符串，可选，必须存在)
    "title": "按类别分组的销售额趋势" // 图表标题
}}

注意事项：
1.  `chart_type` 必须是 `bar`, `line`, `pie`, `scatter` 中的一个。
2.  `x_axis`, `y_axis`, `group_by` (如果提供) 都必须是数据中存在的列名。
3.  **只有当 `chart_type` 为 `line` 且需要按组绘制多条线时，才需要提供 `group_by`。**
4.  `y_axis` 在按组绘线时，通常是一个数值列。
5.  `group_by` 列通常是分类列。
6.  只返回指定的 JSON 对象。
"""
        return prompt

    def extract_json_from_response(self, content: str):
        """
        从大模型的回复中提取JSON配置
        """
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            json_pattern = r'```(?:json)?\s*({.*?})\s*```'
            match = re.search(json_pattern, content, re.DOTALL)
            if match:
                json_str = match.group(1)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1 and start < end:
                json_str = content[start:end + 1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            raise ValueError("无法从回复中提取有效的JSON配置")

    def generate_chart_config(self, df, user_request) -> dict:
        """
        调用大模型，获取图表类型和配置建议
        """
        start_time = time.time()

        message_log = [
            {
                "role": "user",
                "content": self.build_llm_prompt(df, user_request)
            }
        ]

        llm_response = generation(config["model"], config["api_url"], config["api_key"], message_log)
        print(f"LLM 原始响应: {llm_response}")

        try:
            # 尝试解析 LLM 返回的 JSON
            chart_config = self.extract_json_from_response(llm_response)
            print(f"解析后的图表配置: {chart_config}")
        except ValueError as e:
            print(f"解析 LLM JSON 失败: {e}")
            # --- 移除了回退逻辑 ---
            # 直接抛出异常或返回一个默认的错误配置
            raise e  # 或者返回一个默认配置，例如：
            # chart_config = {"chart_type": "bar", "x_axis": None, "y_axis": None, "group_by": None, "title": "图表生成失败"}

        print(f"generate_chart_config 运行时间: {time.time() - start_time:.2f}秒")
        return chart_config

    def create_matplotlib_chart(self, dataframe: pd.DataFrame, chart_config: dict, filename: str):
        """
        根据解析出的配置和数据，使用 matplotlib 创建并保存图表。
        """
        try:
            chart_type = chart_config.get("chart_type", "bar")
            x_col = chart_config.get("x_axis")
            y_col = chart_config.get("y_axis")
            group_col = chart_config.get("group_by")  # 新增: 获取分组列
            title = chart_config.get("title", "图表")

            print(f"尝试创建图表: 类型={chart_type}, X轴={x_col}, Y轴={y_col}, 分组={group_col}, 标题={title}")

            # --- 验证列名是否存在 ---
            required_cols = [x_col, y_col]
            if group_col:
                required_cols.append(group_col)

            for col in required_cols:
                if col and col not in dataframe.columns:
                    raise ValueError(f"指定的列 '{col}' 在数据中不存在。")

            # 确保 y_col 是数值型
            if y_col and not pd.api.types.is_numeric_dtype(dataframe[y_col]):
                raise ValueError(f"Y 轴列 '{y_col}' 必须是数值类型。")

            # --- 绘图逻辑 ---
            plt.figure(figsize=(10, 6))

            if chart_type == "line":
                if x_col and y_col:
                    # --- 按 group_col 分组绘制多条线 ---
                    if group_col:
                        # 1. 按 group_col 分组
                        grouped = dataframe.groupby(group_col)

                        # 2. 遍历每个组
                        for name, group in grouped:
                            # 3. 对每个组内的数据按 x 轴排序
                            sorted_group = group.sort_values(by=x_col)
                            # 4. 绘制该组的线，使用 name 作为 label
                            plt.plot(sorted_group[x_col], sorted_group[y_col], marker='o', label=str(name))

                        # 5. 添加图例
                        plt.legend(title=group_col)

                    # --- 不分组，绘制单条线 ---
                    else:
                        sorted_df = dataframe.sort_values(by=x_col) if (pd.api.types.is_datetime64_any_dtype(
                            dataframe[x_col]) or pd.api.types.is_numeric_dtype(dataframe[x_col])) else dataframe
                        plt.plot(sorted_df[x_col], sorted_df[y_col], marker='o')

                    plt.xlabel(x_col)
                    plt.ylabel(y_col)
                    plt.xticks(rotation=45, ha='right')

                else:
                    raise ValueError("折线图需要明确的 X 轴和 Y 轴列。")

            # --- 其他图表类型的处理 ---
            elif chart_type == "pie":
                if x_col and y_col:
                    # 饼图通常需要对数据进行聚合
                    grouped_df = dataframe.groupby(x_col)[y_col].sum().reset_index()
                    labels = grouped_df[x_col].astype(str).tolist()
                    sizes = grouped_df[y_col].tolist()
                    plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
                    plt.axis('equal')
                else:
                    # Fallback: 如果列不明确，对第一列做计数
                    col_to_count = x_col if x_col else (dataframe.columns[0] if len(dataframe.columns) > 0 else None)
                    if col_to_count:
                        counts = dataframe[col_to_count].value_counts()
                        plt.pie(counts.values, labels=counts.index.astype(str), autopct='%1.1f%%', startangle=90)
                        plt.axis('equal')
                        title = f"{col_to_count} 分布"
                    else:
                        raise ValueError("无法为饼图确定数据列。")

            elif chart_type == "scatter":
                if x_col and y_col:
                    plt.scatter(dataframe[x_col], dataframe[y_col], alpha=0.7)
                    plt.xlabel(x_col)
                    plt.ylabel(y_col)
                else:
                    raise ValueError("散点图需要明确的 X 轴和 Y 轴列。")

            elif chart_type == "bar":
                if x_col and y_col:
                    # 柱状图通常也需要聚合
                    grouped_df = dataframe.groupby(x_col)[y_col].mean().reset_index()  # 或 .sum()
                    plt.bar(grouped_df[x_col].astype(str), grouped_df[y_col])
                    plt.xlabel(x_col)
                    plt.ylabel(f"平均 {y_col}")  # 根据聚合方式调整
                    plt.xticks(rotation=45, ha='right')
                else:
                    # Fallback
                    numeric_cols = dataframe.select_dtypes(include=[np.number]).columns.tolist()
                    if numeric_cols:
                        col_to_plot = numeric_cols[0]
                        plt.hist(dataframe[col_to_plot], bins=20)
                        plt.xlabel(col_to_plot)
                        plt.ylabel("频率")
                        title = f"{col_to_plot} 分布直方图"
                    else:
                        raise ValueError("柱状图需要 X 轴和 Y 轴列，或至少一列数值数据。")
            else:
                # 对于未明确支持的类型，尝试绘制柱状图
                print(f"警告: 不支持的图表类型 '{chart_type}'，将尝试绘制柱状图。")
                if x_col and y_col:
                    grouped_df = dataframe.groupby(x_col)[y_col].mean().reset_index()
                    plt.bar(grouped_df[x_col].astype(str), grouped_df[y_col])
                    plt.xlabel(x_col)
                    plt.ylabel(f"平均 {y_col}")
                    plt.xticks(rotation=45, ha='right')
                    title = f"({chart_type}) {title}"
                else:
                    raise ValueError(f"无法为图表类型 '{chart_type}' 确定绘图数据。")

            plt.title(title)
            plt.tight_layout()
            plt.savefig(filename, dpi=150, bbox_inches='tight')
            plt.close()
            print(f"图表已成功保存至: {filename}")

        except Exception as e:
            print(f"使用 matplotlib 创建图表时出错: {e}")
            # 创建一个错误提示图
            plt.figure(figsize=(8, 4))
            plt.text(0.5, 0.5, f'图表生成错误:\n{str(e)}', ha='center', va='center', transform=plt.gca().transAxes,
                     wrap=True, fontsize=10)
            plt.title("图表生成失败", fontsize=12)
            plt.axis('off')
            plt.tight_layout()
            plt.savefig(filename, dpi=150, bbox_inches='tight')
            plt.close()
            # 重新抛出异常，让上层知道
            # raise # 可选：如果你想让整个流程因图表失败而停止

    def create_fault_visualizations(self, user_request, df, temp_dir):
        """
        主要的可视化创建入口
        """
        path = os.path.join(temp_dir, "sql_data_analysis.png")

        # 1. 获取 LLM 的图表建议
        chart_config = self.generate_chart_config(df=df, user_request=user_request)

        start_time = time.time()
        # 2. 使用 matplotlib 创建图表
        self.create_matplotlib_chart(dataframe=df, chart_config=chart_config, filename=path)

        print(f"create_fault_visualizations 运行时间: {time.time() - start_time:.2f}秒")
        return path

    def add_markdown_with_plots(self, doc, markdown_text, plot_path):
        start_time = time.time()
        html = markdown.markdown(markdown_text)
        soup = BeautifulSoup(html, 'html.parser')

        # 添加列表状态跟踪
        in_ordered_list = False
        in_unordered_list = False

        for element in soup.children:
            if not element.name:
                continue

            if element.name == 'p':
                # 结束之前的列表
                if in_ordered_list or in_unordered_list:
                    in_ordered_list = False
                    in_unordered_list = False

                paragraph = doc.add_paragraph()
                for child in element.children:
                    if hasattr(child, 'name') and child.name == 'strong':
                        run = paragraph.add_run(child.get_text())
                        run.bold = True
                    else:
                        text = child if isinstance(child, str) else child.get_text()
                        if text.strip():
                            paragraph.add_run(text)

            elif element.name in ['h1', 'h2', 'h3']:
                # 结束之前的列表
                if in_ordered_list or in_unordered_list:
                    in_ordered_list = False
                    in_unordered_list = False

                level = int(element.name[1]) - 1
                doc.add_heading(element.get_text(), level=level)

            elif element.name == 'ul':
                # 结束之前的列表
                if in_ordered_list:
                    in_ordered_list = False

                in_unordered_list = True
                for li in element.find_all('li'):
                    # 使用Word的列表样式而不是手动添加符号
                    paragraph = doc.add_paragraph(style='List Bullet')
                    paragraph.add_run(li.get_text())

            elif element.name == 'ol':
                # 结束之前的列表
                if in_unordered_list:
                    in_unordered_list = False

                in_ordered_list = True
                for i, li in enumerate(element.find_all('li'), start=1):
                    # 使用Word的列表样式而不是手动添加数字
                    paragraph = doc.add_paragraph(style='List Number')
                    paragraph.add_run(li.get_text())

            elif element.name == 'blockquote':
                # 结束之前的列表
                if in_ordered_list or in_unordered_list:
                    in_ordered_list = False
                    in_unordered_list = False

                p = doc.add_paragraph(style="Intense Quote")
                p.add_run(element.get_text()).italic = True

            elif element.name == 'hr':
                # 结束之前的列表
                if in_ordered_list or in_unordered_list:
                    in_ordered_list = False
                    in_unordered_list = False

                doc.add_paragraph("―" * 50)

        # 确保所有列表都已结束
        in_ordered_list = False
        in_unordered_list = False

        if plot_path and os.path.exists(plot_path):
            doc.add_paragraph()
            doc.add_picture(plot_path, width=Inches(6))
            doc.add_paragraph("图: 故障数据分析图表").alignment = 1

        print(f"add_markdown_with_plots 运行时间: {time.time() - start_time:.2f}秒")

    def generate_report_text(self, df,user_request):
        start_time = time.time()
        prompt = GENERATE_REPORT_PROMPT.format(df=df,user_question=user_request)
        payload = [
            {
                "role": "user",
                "content": prompt
            }
        ]
        result = generation(config["model"], config["api_url"], config["api_key"], payload)
        print(f"generate_report_text 运行时间: {time.time() - start_time:.2f}秒")
        return result

    def generate_fault_report(self, df, user_request):
        start_time = time.time()
        with tempfile.TemporaryDirectory() as temp_dir:
            # 使用线程池并行执行报告文本生成和可视化生成
            with ThreadPoolExecutor(max_workers=2) as executor:
                # 提交两个任务
                report_future = executor.submit(self.generate_report_text, df,user_request)
                visualization_future = executor.submit(self.create_fault_visualizations, user_request, df, temp_dir)

                # 等待并获取结果
                report_text_start = time.time()
                report_text = report_future.result()
                print(f"报告文本生成时间: {time.time() - report_text_start:.2f}秒")

                visualization_start = time.time()
                plot_path = visualization_future.result()
                print(f"可视化生成时间: {time.time() - visualization_start:.2f}秒")

            doc_creation_start = time.time()
            doc = Document()

            # doc.add_heading("轨道交通故障缺陷分析报告", 0)
            # doc.add_paragraph("机密文件 - 仅供内部使用")
            # doc.add_paragraph(f"报告生成时间: {datetime.now().strftime('%Y年%m月%d日')}")
            # doc.add_page_break()

            self.add_markdown_with_plots(doc, report_text, plot_path)

            if not df.empty:
                doc.add_heading("详细故障数据", level=2)
                display_df = df.head(100)

                table = doc.add_table(display_df.shape[0] + 1, display_df.shape[1])

                for j, column in enumerate(display_df.columns):
                    table.cell(0, j).text = str(column)

                for i, row in enumerate(display_df.itertuples(), start=1):
                    for j, value in enumerate(row[1:], start=0):
                        table.cell(i, j).text = str(value)

                table.style = "LightShading-Accent1"
            doc.save('test.docx')
            doc_bytes = BytesIO()
            doc.save(doc_bytes)
            doc_bytes.seek(0)

            print(f"文档创建时间: {time.time() - doc_creation_start:.2f}秒")
            print(f"generate_fault_report 总运行时间: {time.time() - start_time:.2f}秒")

            return doc_bytes.getvalue()


if __name__ == "__main__":
    # --- 示例使用 ---
    report_generator = ReportGenerator()