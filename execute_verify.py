#!/usr/bin/env python3
# =============================================================================
# GitHub Asset Compliance Verification Script
# GitHub资产合规性验证脚本（支持文件、结构、内容、提交验证）
# 依赖: requests, python-dotenv (需提前安装：pip install requests python-dotenv)
# 配置说明：通过修改 VERIFICATION_CONFIG 字典适配不同验证需求
# =============================================================================

import sys
import os
import requests
import base64
import re
from typing import Dict, List, Optional, Tuple, Callable
from dotenv import load_dotenv

# =============================================================================
# 1. 配置部分 - 根据实际需求修改以下配置
# =============================================================================

# 环境配置
ENV_CONFIG = {
    "env_file_name": ".mcp_env",  # 环境变量文件名
    "github_token_var": "MCP_GITHUB_TOKEN",  # GitHub令牌环境变量名
    "github_org_var": "GITHUB_EVAL_ORG",  # GitHub组织/用户名环境变量名
}

# GitHub API 配置
GITHUB_API_CONFIG = {
    "api_accept_format": "application/vnd.github.v3+json",  # API响应格式
    "success_status_code": 200,  # API成功状态码
    "not_found_status_code": 404,  # 资源未找到状态码
    "default_branch": "main",  # 仓库默认分支
    "file_encoding": "utf-8",  # 仓库文件编码
    "commit_search_max_count": 10,  # 提交记录最大查询数量
    "regex_match_flag": "IGNORECASE",  # 提交消息正则匹配模式
}

# 验证流程配置
VERIFICATION_FLOW_CONFIG = {
    "step_number_format": {
        "file_existence": "1/5",  # 文件存在性验证步骤序号
        "environment_check": "1/5",  # 环境检查步骤序号
        "file_structure": "2/5",  # 文件结构验证步骤序号
        "content_accuracy": "3/5",  # 内容准确性验证步骤序号
        "commit_record": "4/5",  # 提交记录验证步骤序号
    },
    "separator_length": 50,  # 输出分隔符长度
    "success_message": "✅ 所有验证步骤通过！",  # 最终成功提示文本
    "exit_code": {
        "success": 0,  # 验证成功退出码
        "failure": 1  # 验证失败退出码
    },
}

# 验证配置 - 根据实际需求修改以下内容
VERIFICATION_CONFIG = {
    # 目标仓库信息
    "target_repo": "project-analysis",  # 替换为你的仓库名
    
    # 目标文件信息（需验证的文件）
    "target_file": {
        "path": "document/analysis-report.md",  # 替换为你的文件路径
        "branch": "main"  # 替换为目标分支
    },
    
    # 必需结构（文件必须包含的内容，如章节标题、表格头部）
    "required_structures": [
        "# 项目分析报告",  # 替换为你的必需标题
        "## 汇总统计",  # 替换为你的必需章节
        "| 指标 | 数值 |"  # 替换为你的必需表格头部
    ],
    
    # 内容验证规则（支持 stat_match/regex_match/text_match，可增删）
    "content_rules": [
        # 规则1：代码行数统计
        {
            "type": "stat_match",
            "target": "代码行数",
            "expected": "15800"
        },
        # 规则2：提交次数统计
        {
            "type": "stat_match",
            "target": "提交次数",
            "expected": "324"
        },
        # 规则3：团队成员统计
        {
            "type": "stat_match",
            "target": "团队成员",
            "expected": "8"
        },
        # 规则4：正则匹配
        {
            "type": "regex_match",
            "target": "团队成员邮箱",
            "expected": r"\w+@\w+\.\w+"  # 匹配通用邮箱格式
        },
        # 规则5：固定文本匹配
        {
            "type": "text_match",
            "target": "项目状态",
            "expected": "项目状态：已完成"
        }
    ],
    
    # 提交记录验证（可选，支持模糊匹配）
    "commit_verification": {
        "msg_pattern": "项目报告|document|update",  # 提交消息关键词
        "max_commits": 10  # 搜索最近N条提交
    }
}

# =============================================================================
# 2. 通用工具函数（无需修改，直接复用）
# =============================================================================

def load_environment() -> Tuple[Optional[str], Optional[str]]:
    """加载环境变量：GitHub访问令牌和目标组织/用户名"""
    load_dotenv(ENV_CONFIG["env_file_name"])
    github_token = os.environ.get(ENV_CONFIG["github_token_var"])
    github_org = os.environ.get(ENV_CONFIG["github_org_var"])
    return github_token, github_org

def build_request_headers(github_token: str) -> Dict[str, str]:
    """构建GitHub API请求头（含授权信息）"""
    return {
        "Authorization": f"Bearer {github_token}",
        "Accept": GITHUB_API_CONFIG["api_accept_format"]
    }

def call_github_api(
    endpoint: str,
    headers: Dict[str, str],
    org: str,
    repo: str
) -> Tuple[bool, Optional[Dict]]:
    """调用GitHub API并返回（请求状态，响应数据）"""
    url = f"https://api.github.com/repos/{org}/{repo}/{endpoint}"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == GITHUB_API_CONFIG["success_status_code"]:
            return True, response.json()
        elif response.status_code == GITHUB_API_CONFIG["not_found_status_code"]:
            print(f"[API 提示] {endpoint} 资源未找到（{GITHUB_API_CONFIG['not_found_status_code']}）", file=sys.stderr)
            return False, None
        else:
            print(f"[API 错误] {endpoint} 状态码：{response.status_code}", file=sys.stderr)
            return False, None
    except Exception as e:
        print(f"[API 异常] 调用 {endpoint} 失败：{str(e)}", file=sys.stderr)
        return False, None

def get_repository_file_content(
    file_path: str,
    headers: Dict[str, str],
    org: str,
    repo: str,
    branch: str = GITHUB_API_CONFIG["default_branch"]
) -> Optional[str]:
    """获取指定分支下的文件内容（Base64解码）"""
    success, result = call_github_api(
        f"contents/{file_path}?ref={branch}", headers, org, repo
    )
    if not success or not result:
        return None
    try:
        return base64.b64decode(result.get("content", "")).decode(GITHUB_API_CONFIG["file_encoding"])
    except Exception as e:
        print(f"[文件解码错误] {file_path}：{str(e)}", file=sys.stderr)
        return None

def search_commits(
    headers: Dict[str, str],
    org: str,
    repo: str,
    commit_msg_pattern: str,
    max_commits: int = GITHUB_API_CONFIG["commit_search_max_count"]
) -> bool:
    """搜索包含指定消息模式的提交记录（支持模糊匹配）"""
    success, commits = call_github_api(
        f"commits?per_page={max_commits}", headers, org, repo
    )
    if not success:
        return False
    for commit in commits:
        if re.search(commit_msg_pattern, commit["commit"]["message"], re.IGNORECASE):
            return True
    return False

# =============================================================================
# 3. 验证逻辑函数
# =============================================================================

def verify_environment_setup() -> Tuple[bool, Optional[str], Optional[str]]:
    """验证环境配置是否正确"""
    print(f"[{VERIFICATION_FLOW_CONFIG['step_number_format']['environment_check']}] 验证环境配置...")
    
    github_token, github_org = load_environment()
    
    if not github_token:
        print(f"[环境错误] 未配置 {ENV_CONFIG['github_token_var']}（需在 {ENV_CONFIG['env_file_name']} 中设置）", file=sys.stderr)
        return False, None, None
    
    if not github_org:
        print(f"[环境错误] 未配置 {ENV_CONFIG['github_org_var']}（需在 {ENV_CONFIG['env_file_name']} 中设置）", file=sys.stderr)
        return False, None, None
    
    print(f"[成功] 环境配置正确")
    return True, github_token, github_org

def verify_file_existence(
    headers: Dict[str, str],
    org: str,
    repo: str,
    file_path: str,
    branch: str
) -> Tuple[bool, Optional[str]]:
    """验证目标文件是否存在于指定分支"""
    print(f"[{VERIFICATION_FLOW_CONFIG['step_number_format']['file_existence']}] 验证文件存在性：{file_path}（分支：{branch}）...")
    
    content = get_repository_file_content(file_path, headers, org, repo, branch)
    if not content:
        print(f"[错误] 文件 {file_path} 在 {branch} 分支中未找到", file=sys.stderr)
        return False, None
    
    print(f"[成功] 文件 {file_path} 存在")
    return True, content

def verify_file_structure(content: str, required_structures: List[str]) -> bool:
    """验证文件是否包含必需的结构（如章节、关键词、表格头部）"""
    print(f"[{VERIFICATION_FLOW_CONFIG['step_number_format']['file_structure']}] 验证文件结构：共需包含 {len(required_structures)} 个必需结构...")
    
    missing = []
    for struct in required_structures:
        if struct not in content:
            missing.append(struct)
    
    if missing:
        print(f"[错误] 缺失必需结构：{', '.join(missing)}", file=sys.stderr)
        return False
    
    print(f"[成功] 所有必需结构均存在")
    return True

def verify_content_accuracy(content: str, content_rules: List[Dict]) -> bool:
    """验证文件内容是否符合预期规则（如统计数据、正则匹配、枚举值）"""
    if not content_rules:
        print(f"[{VERIFICATION_FLOW_CONFIG['step_number_format']['content_accuracy']}] 跳过] 未配置内容验证规则，直接通过")
        return True
    
    print(f"[{VERIFICATION_FLOW_CONFIG['step_number_format']['content_accuracy']}] 验证内容准确性：共需校验 {len(content_rules)} 条规则...")
    lines = content.split("\n")
    
    for rule in content_rules:
        rule_type = rule["type"]
        target = rule["target"]
        expected = rule["expected"]
        matched = False
        
        # 规则1：统计数据匹配（如"项目总数：100"）
        if rule_type == "stat_match":
            for line in lines:
                if target in line:
                    # 提取数字（支持整数/小数）
                    match = re.search(r"(\d+(?:\.\d+)?)", line)
                    if match and str(match.group(1)) == str(expected):
                        matched = True
                        break
                if matched:
                    break
        
        # 规则2：正则匹配（如邮箱、手机号、枚举值）
        elif rule_type == "regex_match":
            if re.search(expected, content):
                matched = True
        
        # 规则3：固定文本匹配（如"状态：已完成"）
        elif rule_type == "text_match":
            if expected in content:
                matched = True
        
        if not matched:
            print(f"[错误] 内容规则校验失败：{target} 预期 {expected}，实际未匹配", file=sys.stderr)
            return False
    
    print(f"[成功] 所有内容规则校验通过")
    return True

def verify_commit_record(
    headers: Dict[str, str],
    org: str,
    repo: str,
    commit_msg_pattern: str,
    max_commits: int
) -> bool:
    """验证仓库是否存在符合预期的提交记录"""
    print(f"[{VERIFICATION_FLOW_CONFIG['step_number_format']['commit_record']}] 验证提交记录：搜索包含「{commit_msg_pattern}」的最近 {max_commits} 条提交...")
    
    found = search_commits(headers, org, repo, commit_msg_pattern, max_commits)
    if not found:
        print(f"[错误] 未找到符合要求的提交记录", file=sys.stderr)
        return False
    
    print(f"[成功] 找到符合要求的提交记录")
    return True

# =============================================================================
# 4. 主验证流程（入口函数）
# =============================================================================

def run_verification_process(verification_config: Dict) -> bool:
    """执行完整验证流程：环境检查 → 文件存在 → 结构验证 → 内容验证 → 提交验证"""
    # 打印开始信息
    separator = "=" * VERIFICATION_FLOW_CONFIG["separator_length"]
    print(separator)
    print("开始执行GitHub资产合规性验证")
    print(separator)
    
    # 步骤1：环境检查
    env_ok, github_token, github_org = verify_environment_setup()
    if not env_ok:
        return False
    
    repo_name = verification_config["target_repo"]
    headers = build_request_headers(github_token)
    print(f"[环境就绪] 目标仓库：{github_org}/{repo_name}\n")
    
    # 步骤2：验证文件存在性
    file_path = verification_config["target_file"]["path"]
    branch = verification_config["target_file"]["branch"]
    file_exists, file_content = verify_file_existence(headers, github_org, repo_name, file_path, branch)
    if not file_exists:
        return False
    
    # 步骤3：验证文件结构
    structure_valid = verify_file_structure(file_content, verification_config["required_structures"])
    if not structure_valid:
        return False
    
    # 步骤4：验证内容准确性
    content_valid = verify_content_accuracy(file_content, verification_config["content_rules"])
    if not content_valid:
        return False
    
    # 步骤5：验证提交记录
    commit_config = verification_config.get("commit_verification")
    if commit_config:
        commit_valid = verify_commit_record(
            headers, 
            github_org, 
            repo_name, 
            commit_config["msg_pattern"], 
            commit_config.get("max_commits", GITHUB_API_CONFIG["commit_search_max_count"])
        )
        if not commit_valid:
            return False
    else:
        print(f"[{VERIFICATION_FLOW_CONFIG['step_number_format']['commit_record']}] 跳过] 未配置提交验证规则，直接通过")
    
    # 所有步骤通过
    print("\n" + separator)
    print(VERIFICATION_FLOW_CONFIG["success_message"])
    print(f"验证对象：{file_path}")
    print(f"目标仓库：{github_org}/{repo_name}")
    print(f"验证分支：{branch}")
    print(f"通过规则数：{len(verification_config['required_structures']) + len(verification_config['content_rules'])}")
    if commit_config:
        print(f"匹配提交消息：{commit_config['msg_pattern']}")
    print(separator)
    
    return True

# =============================================================================
# 5. 主程序入口
# =============================================================================

if __name__ == "__main__":
    # 执行验证并返回结果
    success = run_verification_process(VERIFICATION_CONFIG)
    sys.exit(VERIFICATION_FLOW_CONFIG["exit_code"]["success"] if success else VERIFICATION_FLOW_CONFIG["exit_code"]["failure"])
