# TeamSTEPPS MAS

用于协作开发的医学多智能体研究代码。采用 MedAgents 的专科招募与终答提示，在本项目中实现共享任务、专科工作、临床交叉监测、原意核对、huddle 和任务协助控制。当前包对应 V16 候选实现；研究草案与实际实现的差异见[设计说明](docs/design.md)。

本仓库保存核心代码、提示词、接口合同、环境配置和合成工程测试。实验过程文档、结果、真实评测数据、模型权重与凭据保存在各自本地目录，不纳入版本管理。

## 从哪里开始

| 内容 | 入口 |
|---|---|
| 整体问题、架构与实现边界 | [核心设计](docs/design.md) |
| 消息、状态、原始调用和通信范围 | [协议说明](docs/protocol.md) |
| Python、MedAgents、模型与语法服务 | [环境配置](docs/environment.md) |
| 输入格式与本地运行 | [数据与运行接口](docs/data.md) |
| 代码分工、修改检查与协作方式 | [开发指南](CONTRIBUTING.md) |
| 上游来源与版本 | [第三方说明](THIRD_PARTY_NOTICES.md)、[固定版本](configs/upstream.json) |

## 安装与检查

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements/client.txt
python -m pip install -e .
python scripts/check_environment.py
python -m unittest discover -s tests -v
teamstepps-mas --input examples/synthetic_case.jsonl --dry-run
```

上述检查只使用合成输入和脚本回复，不访问模型或 GPU。需要模型运行时，按[环境文档](docs/environment.md)安装上游源码、启动模型和语法服务，再执行：

```bash
teamstepps-mas \
  --input examples/synthetic_case.jsonl \
  --out runs/local_example \
  --methods native_medagents,teamstepps \
  --base-url http://127.0.0.1:8000/v1 \
  --model qwen3-8b
```

`--out`必须是新目录。运行器不自动重试推理，也不额外调用模型进行语法修复；后端失联时停止后续派发，并保留尚未执行的位置。它是顺序开发入口，不会启动或关闭GPU服务，也不会生成准确率或临床质量评分。

## 代码地图

```text
src/teamstepps_mas/
  protocol.py          TeamSTEPPS控制器与组件开关
  contracts.py         动态JSON逻辑合同
  exchange.py          明确来源、定向视图与可逆消息池
  upstream.py          MedAgents提示和原生syn_verif适配
  grammar.py           逻辑/物理schema与语法编译桥
  runtime.py           模型调用、原始trace和usage记账
  parsing.py           明确选项解析
  cli.py               本地输入检查与顺序运行
  prompts/default.json 当前候选提示词和输出上限
configs/               可移植开发配置与上游版本
scripts/               上游安装、语法服务和环境检查
tests/                 合成协议场景与后端中断检查
docs/                  核心设计、接口和环境文档
```

支持的条件为原生 MedAgents、generic team、meaning only、assistance only、TeamSTEPPS、全文广播和未池化 TeamSTEPPS。它们是实现开关，不能仅凭名称视为等算力比较或已证明有效的机制。其他公开 MAS 的历史适配未打包成此入口，后续可在独立模块中接入。

当前控制器类从原研究代码原样迁移，整理了包导入、资源路径和服务地址配置；未把新的协议草案伪装成已实现功能。[迁移来源](docs/code_provenance.json)不包含实验结果。当前代码是研究原型，模型认可、格式合法和消息送达都不等于医学正确或实际采用。
