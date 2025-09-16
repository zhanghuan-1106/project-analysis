# GitHub 资产合规性验证工具

## 简介

一个自动化验证脚本，用于检查 GitHub 仓库中的资产（文档、配置文件等）是否符合预设规范。

## 项目结构

```
project-analysis/
├── document/
│   ├── analysis-report.md
├── execute_verifier.py
└── README.md
└── .mcp_env
```

## 安装要求

- Python 3.7+
- 安装依赖：`pip install requests python-dotenv`

## 配置

在 `.mcp_env` 文件中添加：

```
MCP_GITHUB_TOKEN=你的GitHub令牌
GITHUB_EVAL_ORG=你的GitHub组织名或用户名
```

## 使用方法

1. 修改 `execute_verifier.py` 中的 `VERIFICATION_CONFIG` 配置验证规则
2. 运行脚本：`python execute_verifier.py`

## 验证内容

- 环境配置检查
- 目标文件存在性验证
- 文件结构完整性验证
- 内容准确性验证
- 提交记录合规性验证

## 结果输出

- 实时显示验证进度
- 验证成功时输出摘要信息
- 验证失败时输出错误详情
- 成功返回退出码 0，失败返回退出码 1

## 注意事项

- 脚本只读取数据，不会修改仓库内容
- GitHub 令牌需要具有 `repo` 权限
- 所有验证规则可在脚本中灵活配置
