# 协作开发

先读[核心设计](docs/design.md)和[协议](docs/protocol.md)，按[环境说明](docs/environment.md)安装客户端。建议在自己的分支修改，通过PR合并；原始研究目录中的冻结代码和运行归档由各自维护，本仓库不替代实验存档。

## 模块分工

- 控制器与状态：`protocol.py`、`contracts.py`。
- 模型可见提示：`prompts/default.json`；修改时同时说明对应字段合同与实际接收上下文。
- 原生工作与baseline：`upstream.py`；新增公开MAS建议独立适配模块，固定上游版本并记录修改边界。
- 传输与环境：`exchange.py`、`grammar.py`、`runtime.py`及服务脚本。
- 评价：独立开发内容评价器，避免用协议标签直接充当医学质量标签。

## 提交前检查

```bash
python -m unittest discover -s tests -v
python scripts/check_environment.py
teamstepps-mas --input examples/synthetic_case.jsonl --dry-run
git diff --check
git status --short
```

协议变化应有针对性地补充合成场景，例如未解决问题跨轮保留、接管后无法完成、越权关闭、输出截断或通道污染。脚本回复与少量接口联调不作为医学效果证据。真实模型验证另存原始回复、失败、成本、配置及来源版本，不能用后台文本修复或重计费用掩盖失败。

PR说明应写清问题、行为变化、涉及消息、验证范围和仍未实现的内容。保持基础工作接口一致，再比较通信组件；新增知识、检索或强模型编辑需与协议本身的作用分开。

仅提交代码、可移植配置和核心文档。`data/`、`runs/`、`analysis/`、`outputs/`、`provenance/`、模型、凭据及第三方完整克隆已忽略，不使用`git add -f`提交它们。需要共享结果时使用团队约定的独立存储。
