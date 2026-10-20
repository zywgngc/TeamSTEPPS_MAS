# 数据与运行接口

真实数据由每位合作者按其来源和使用条件在本地准备，默认放入忽略的`data/`。本仓库只附一条人为编写的算术输入供接口检查，不包含公开医学数据集的题目、答案或评测结果。

输入为UTF-8 JSONL，每行一个对象：

```json
{
  "id": "synthetic:example",
  "dataset": "synthetic",
  "question": "Which expression matches 20 events among 500 observations?",
  "context": ["Artificial arithmetic fixture; no clinical interpretation."],
  "options": {"A": "4%", "B": "40%", "C": "20%"}
}
```

ID必须唯一；问题和选项文本非空，支持A–E中的二至五个选项。context为可省略的字符串列表。入口只向控制器传递id、dataset、question、context、options白名单；gold、解释和其他评分字段不进入模型输入。对语义泄漏、重复病例及预训练污染仍需在具体数据处理流程中检查。

```bash
# 无模型调用、无输出文件
teamstepps-mas --input data/local_cases.jsonl --methods native_medagents,teamstepps --dry-run

# 模型与语法服务准备好后，使用全新输出目录
teamstepps-mas --input data/local_cases.jsonl --out runs/my_change \
  --methods native_medagents,generic_team,teamstepps
```

同一输入和多个条件按来源顺序逐项新生成，不共享缓存临床轨迹。默认temperature=0、seed=111、non-thinking；不同模型、模板及输出上限的修改必须显式记录。

本地输出包括manifest、逐位置结果、traces和completion。输出可包含完整模型输入，应按数据权限保管。已有输出目录不覆盖、不恢复、不自动补跑；模型失败和尚未执行的位置保持区分。该CLI用于开发与接口联调，尚未提供多卡队列、正式评分、多种子统计或数据集下载器。
