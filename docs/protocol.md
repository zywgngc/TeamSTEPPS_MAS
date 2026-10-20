# 消息与通信协议

## 数据对象

`contracts.py`是当前字段定义的唯一代码入口。`prompts/default.json`包含分阶段提示和输出上限；提示词本身不认证内容正确。

| 对象 | 当前必要内容 |
|---|---|
| 原始来源 | 问题Q、证据E1…、选项O:A…及完整原文 |
| Brief | decision、criterion、逐成员assignments、resources_and_limits |
| 专科工作 | contribution含选择、理由、claims；或outside_role含理由 |
| Claim | statement、evidence_kind、source_ids、rationale、conditions_and_limits |
| 综合 | 当前任务、候选选择、report、critical_uses、逐问题issue_responses |
| Clinical review | concern/no_concern/outside_role、理由及原问题重评 |
| Meaning review | accurate/misrepresented/not_represented/outside_role及原问题重评；可选状态依实际采用决定 |
| Huddle | act/decline/pending；任务owner、issue_ids、operation、task、expected_product |
| 接管与帮助 | accept/cannot_perform，随后completed/unable_to_complete与实际产出 |
| 终答上下文 | 当前报告、被采用主张、未决问题和任务状态 |

`evidence_kind`区分given_case、calculation、background_inference、predicted_finding、unavailable。合法source_id只说明引用可定位，不说明该命题得到来源支持。

## 过程与状态

1. 作者提示招募问题分析和选项分析成员，生成共享brief。
2. 各成员执行工作；选项成员可见已有问题阶段工作。
3. 综合者声明影响决策的主张及解释。未选择的工作保持可追溯，不补记采用。
4. 分开进行临床交叉监测与原发送者原意核对。
5. 有开放问题且未达上限时，huddle决定后续任务；接受与实际工作是两个调用。
6. 产出进入新综合及原提出者复核。不能仅以计划、接管或文本变化判定完成。
7. 最终选项调用仍接收原题与选项，未决状态继续可见。

程序检查原提出者与通道身份，越权反馈被拒绝；outside_role不能确认此前问题已处理。TeamSTEPPS合同调用达到长度上限或逻辑schema无效时保留原回复并使当前轨迹失败，不自动补写或重试；原生对照沿用作者控制流，截断信息由公共调用边界单独记录。

## 实际通信范围

定向条件给成员当前相关信息以及其原始工作前缀。全文广播条件额外发送完整逻辑历史，但不把同轮尚未完成的标签送入另一个通道。池化只将重复的完整子对象替换为payload_ref，所有被引用内容在同一消息的inline_payloads中。`unpool`必须能精确恢复原逻辑对象；不存在通过ID进行外部查询。

传输恢复与内容理解是不同问题。不能把成功unpool记成“理解准确”，不能把not_represented记成成功check-back，也不能把未调用的帮助步骤记成“无需帮助”的医学判断。

## 调用记录

`runtime.py`保存实际request、原response、finish_reason、usage、响应ID和时延；HTTP失败额外保存原状态码和响应体。控制器在相邻sidecar中保存typed_request、message_received/message_rejected、report_delivered、assistance等事件，并绑定原始record_index和内容hash。每条模型回复保持原样；usage缺失不能补作免费调用。当前入口不生成临床正确率，HTTP后端失败后剩余位置保持pending。

## 条件开关

| CLI名称 | 原意核对 | 任务协助 | 历史范围 | 池化 |
|---|---|---|---|---|
| native_medagents | 作者原流程 | 作者原流程 | 作者原流程 | 无新增池化 |
| generic_team | 关 | 关 | 定向 | 是 |
| meaning_only | 开 | 关 | 定向 | 是 |
| assistance_only | 关 | 开 | 定向 | 是 |
| teamstepps | 开 | 开 | 定向 | 是 |
| full_broadcast | 开 | 开 | 全逻辑历史 | 是 |
| unpooled_teamstepps | 开 | 开 | 定向 | 否 |

派生条件均保留brief和临床复核。generic/meaning-only仍可对开放问题生成计划或报告响应，但不分派帮助工作；“关闭任务协助”不表示删除所有协调调用。原生对照保留作者syn_verif控制流，适配本地模型边界，短调用至少128token、分析至少2048token，原有较大上限保持；派生合同的各阶段上限见提示词JSON。两者共用明确选项解析，但不能直接称为原论文分数复现或等算力对照。
