# 第三方来源

## MedAgents

上游：[gersteinlab/MedAgents](https://github.com/gersteinlab/MedAgents)，论文：[MedAgents: Large Language Models as Collaborators for Zero-shot Medical Reasoning](https://arxiv.org/abs/2311.10537)。本项目固定源码commit于`configs/upstream.json`。

当前代码通过独立克隆读取作者`prompt_generator.py`，原生参照动态调用`utils.py`中的`fully_decode`。我们提供本地模型调用适配、宽输出上限与共同选项解析；派生TeamSTEPPS流程由本项目实现。上游源码、数据、图片和完整仓库未重新分发，权利及使用条件由其原作者与来源保留。

## TeamSTEPPS

原则来源为[AHRQ TeamSTEPPS](https://www.ahrq.gov/teamstepps-program/index.html)。本项目引用其公开说明并进行研究性迁移，没有将官方课程内容复制成项目代码，也不表示AHRQ认可或验证本实现。

## 服务与依赖

HTTP客户端使用httpx，逻辑合同使用jsonschema；可选编译服务使用[XGrammar](https://github.com/mlc-ai/xgrammar)，模型服务使用[vLLM](https://github.com/vllm-project/vllm)。这些包通过正常依赖安装，遵循各自许可证。本仓库没有包含模型权重。
