# -*- coding: utf-8 -*-
# @Author   : cz
# @Time     : 2025/7/30 11:27
# @File     : __init__.py.py
# @contact  ： ***
from tools.sqlsearch.vannaer import Vannaer
from config import config
from config import UPLOAD_IP,UPLOAD_PORT,FILE_AGENT_PORT,FILE_AGENT_IP
from generator.ftpsaver import upload_file_to_ftp
from generator.generate import ReportGenerator
report_generator = ReportGenerator()

lanzhou = Vannaer(config=config)
from langchain.tools import tool





@tool
def sqlsearch(query: str) -> str:
    """
    用于在数据库中查询缺陷信息,不需要传入sql
    入参：
        query：用户问题，请直接传入用户问题
    """
    try:
        # 同步调用 lanzhou.ask
        sql, df, fig = lanzhou.ask(
            question=query,
            allow_llm_to_see_data=True,
            auto_train=False,
            visualize=False,

        )
        lenth = len(df)
        if len(df)>20:
            prompt = f'查询数据为{lenth}条，当前仅展示前20条'
        else:
          prompt = ''
        df = df[:20]
        df = df.to_dict('records')
        result = '\n'.join([
            prompt,
            sql,
            str(df)
        ])
        return result

    except Exception as e:
        print(f"sqlsearch 工具执行出错: {e}")
        return f"执行 sqlsearch 时发生错误: {str(e)}"


@tool
def generate_report_bak(query: str) -> str:
    """
    当用户问题中有生成报告的意图时，不论其他工具是否合适，优先调用此工具.因为此工具包含了查询数据的功能，相当于已经调用了数据库查询工具。请勿在工具决策上多花时间。
    入参：
        query：用户问题，请直接传入用户问题
    """
    try:
        # 同步调用 lanzhou.ask
        sql, df, fig = lanzhou.ask(
            question=query,
            allow_llm_to_see_data=True,
            auto_train=False,
            visualize=True
        )

        try:
            file_bytes = report_generator.generate_fault_report(df, fig)
            # 生成图片字节数据
            # 上传到FTP并获取路径
            file_path = upload_file_to_ftp(file_bytes, UPLOAD_IP,UPLOAD_PORT,ext='.docx')
            file_path = file_path.split('/')
            file_path[0] = 'https:'
            file_path[2] = FILE_AGENT_IP + ':'+FILE_AGENT_PORT+'/file'
            file_path = '/'.join(file_path)
        except Exception as e:
            print(f"文件处理失败: {e}")
            file_path = 'None'

        # 构造返回结果
        result = '\n'.join([
            sql,
            str(df),
            "\n\n报告链接如下，请直接输出以下链接：" + f"[点击查看报告]{file_path}"
        ])
        return result

    except Exception as e:
        print(f"sqlsearch 工具执行出错: {e}")
        return f"执行 sqlsearch 时发生错误: {str(e)}"

@tool
def generate_report(query: str) -> str:
    """
    当用户问题中有生成报告的意图时，不论其他工具是否合适，优先调用此工具.因为此工具包含了查询数据的功能，相当于已经调用了数据库查询工具。请勿在工具决策上多花时间。
    入参：
        query：用户问题，请直接传入用户问题
    """
    try:
        # 同步调用 lanzhou.ask
        sql, df, fig = lanzhou.ask(
            question=query,
            allow_llm_to_see_data=True,
            auto_train=False,
            visualize=False
        )



        # 添加背景渐变 + 网格线

        try:
            file_bytes = report_generator.generate_fault_report(df=df,user_request=query)
            # 生成图片字节数据
            # 上传到FTP并获取路径
            file_path = upload_file_to_ftp(file_bytes, UPLOAD_IP,UPLOAD_PORT,ext='.docx')
            file_path = file_path.split('/')
            file_path[0] = 'https:'
            file_path[2] = FILE_AGENT_IP + ':'+FILE_AGENT_PORT+'/file'
            file_path = '/'.join(file_path)
        except Exception as e:
            print(f"文件处理失败: {e}")
            file_path = 'None'

        # 构造返回结果
        result = '\n'.join([
            sql,
            str(df),
            "\n\n报告链接如下，请直接输出以下链接：" + f"[点击查看报告]{file_path}"
        ])
        return result

    except Exception as e:
        print(f"sqlsearch 工具执行出错: {e}")
        return f"执行 sqlsearch 时发生错误: {str(e)}"




def sql_train(question,ddl,documentation,sql):
    return lanzhou.train(question=question,ddl=ddl,documentation=documentation,sql=sql)


if __name__ == '__main__':
    res = generate_report('分析2024各部门的日计划报告数量的变化趋势')
    print(res)