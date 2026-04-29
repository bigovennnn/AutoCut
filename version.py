"""
AutoCut2 Version Management
遵循语义化版本 (Semantic Versioning)
"""

__version__ = "2.2.0"

# 版本号格式: MAJOR.MINOR.PATCH
# - MAJOR: 不兼容的重大架构变更
# - MINOR: 向后兼容的新功能添加
# - PATCH: 向后兼容的问题修复

# 更新日志类型
UPDATE_TYPES = {
    "major": "破坏性变更，需要重写或调整依赖",
    "minor": "新增功能，向后兼容",
    "patch": "问题修复，向后兼容"
}

# 当前版本信息
VERSION_INFO = {
    "version": __version__,
    "major": 2,
    "minor": 2,
    "patch": 0,
    "stage": "stable",  # stable, beta, alpha
    "build": None
}


def next_patch():
    """生成下一个补丁版本"""
    return f"{VERSION_INFO['major']}.{VERSION_INFO['minor']}.{VERSION_INFO['patch'] + 1}"


def next_minor():
    """生成下一个次版本"""
    return f"{VERSION_INFO['major']}.{VERSION_INFO['minor'] + 1}.0"


def next_major():
    """生成下一个主版本"""
    return f"{VERSION_INFO['major'] + 1}.0.0"