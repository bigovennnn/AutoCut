import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate


def find_config_file():
    """
    查找配置文件，支持多种路径策略：
    1. 环境变量 AUTOCUT_CONFIG 指定的路径
    2. 当前目录下的 config.env
    3. 项目根目录下的 AutoCut/config.env
    4. 上级目录的 AutoCut/config.env
    """
    if "AUTOCUT_CONFIG" in os.environ:
        config_path = os.environ["AUTOCUT_CONFIG"]
        if os.path.exists(config_path):
            return config_path

    search_paths = [
        "config.env",
        "AutoCut/config.env",
        "../AutoCut/config.env",
    ]

    for path in search_paths:
        if os.path.exists(path):
            return path

    return "config.env"


# 加载环境变量
config_path = find_config_file()
load_dotenv(config_path, encoding="utf-8")


def get_llm():
    """
    初始化统一的大语言模型接口。
    当前通过 API 调用，后续若本地显存吃紧问题解决，改掉 base_url 即可无缝切换本地模型。
    """
    llm = ChatOpenAI(
        model="qwen-turbo",
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        max_tokens=1024,
        temperature=0.8,
    )
    return llm


def get_copywriting_prompt():
    """
    固化文案生成的 Prompt 模板。
    """
    template = """
    你是一位专业的社交媒体文案创作者，擅长根据不同平台和风格创作引人入胜的内容。
    任务：根据以下素材内容解析结果，为{platform}平台创作一段{style}风格的文案。
    
    素材解析结果：
    {content_analysis}
    
    要求：
    1. 文案需紧扣素材内容，绝不凭空捏造。
    2. 语言风格严格符合：{style}。
    3. 如果平台是小红书，请加上适当的 emoji 和 3-5 个相关话题标签。如果平台是朋友圈，请保持口语化、生活化。
    
    请直接输出最终的文案内容，不要包含任何前缀、解释或自我介绍。
    """
    return PromptTemplate(
        input_variables=["platform", "style", "content_analysis"], template=template
    )


# 测试运行
if __name__ == "__main__":
    llm = get_llm()
    print("大模型基建初始化成功，API 连接正常。")
