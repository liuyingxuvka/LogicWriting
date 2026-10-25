# Logic Writing

<p align="center">
  <img src="https://img.shields.io/badge/source-4.0.14-6f42c1" alt="源码版本 4.0.14" />
  <img src="https://img.shields.io/badge/skill-logic--writing-334155" alt="技能 logic-writing" />
  <img src="https://img.shields.io/badge/routes-4-0a7f5a" alt="四条最终路线" />
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="MIT 许可证" />
</p>

<p align="center">
<!-- README HERO START -->
  <img src="./assets/readme-hero/hero.png" alt="Logic Writing 把模型和证据变成读者真正能读的成品" width="100%" />
<!-- README HERO END -->
</p>

一个正式的 Codex 写作技能，统一处理深度调查、学术写作、小说和重证据的
旅行攻略。它只有一个公开入口，每次只选一个最终负责人；需要专业判断时，
仍由相应 Guard 语义负责人通过当前统一入口负责，最后再把内部模型翻译成
人能读懂的话。

## 为什么合在一起

这四类工作确实共享一层能力：判断最后要交付什么、维护唯一负责人、保留
专业技能的判断权、记住成品的真实版本、规划每一部分让读者新明白了什么、
不把内部术语漏进正文，并在最后检查真正交付的文件。

但它们并不共用一个万能大表。调查保留证据语义，小说保留故事语义，旅行
保留时间、可行性和执行语义。合并的是外壳和真正通用的内核，不是把所有
领域压成同一种写法。

小说可用可选的结构化 `voice_contract`（人称和时态）把声音要求交给写作者；没有内容时，声音引用仍保留为明确缺口。

上一步失败且没有所需记录时，直接显示它的第一条错误。绑定或评审证据引用了已消失的正文单元时，会在补任何指纹前停止；须按当前 ArtifactMap 更正引用。

每篇成品只在内容边界里维护自己的证据。ResearchGuard 的研究文件夹保存
来源和措辞许可，收尾只读它的一份 `verdict`。写作上下文只收到
`ReaderBrief.writer_input`，不接收内部台账或专业工具路径。

## 一个入口，四条最终路线

| 最后要交付的东西 | 最终负责人 | 保留下来的强项 |
| --- | --- | --- |
| 调查报告、简报、证据包、决策说明、调查型回答 | `investigation` | 资料深度、观点竞争、关键数字、反面证据、时间/因果链、有边界的结论 |
| 论文、学位论文章节、文献综述、研究计划、实质性学术修订 | `academic-writing` | 结构、引文、修订溯源、图表、Word/PDF 工作流 |
| 故事计划、短篇、小说章节、长篇、系列设定、故事审计或修订 | `fiction-writing` | 转折、场景、承诺兑现、连续性、声音、世界一致性、共享计划—正文绑定 |
| 行程、目的地攻略、路线方案、住宿策略、旅行者适配建议 | `travel-guide` | 有日期的证据、天气/警报、可行性、体力与偏好、住宿、负面证据、可达备选 |

路由看的是“最后交什么”，不是第一步做什么，也不是题材是什么。旅游研究
论文仍是学术；查了历史资料的小说仍是小说；写得像旅程故事的行程仍是旅行。
学术、小说和旅行可以让调查路线补一个明确的证据缺口，但调查不能替父路线
宣布最终完成。重要的未决读者选择会返回 `needs_user_choice`，暂不分配
负责人；先问第一个问题，把用户回答写回 ReaderIntent，再重新路由。
不重要的选择不阻塞。

## “说人话”不是一句口号

共享写作内核要求每个重要单元回答：

- 读者进来时已经知道或以为什么？
- 哪个具体证据、行动、物件、选择或指令改变了这种认识？
- 还有什么没有解决，或者为什么这里已经可以结束？
- 后面哪一个明确单元会用到这个变化？
- 技术词、地方说法、引语、叙述者或人物语言到底属于谁？
- 如果结构重复了，它产生了什么新的升级、对比、代价或解释？
- 当前模型中的哪一行，真正落在成品的哪一段话里？

它会拦住这些常见问题：内部流程词泄漏、只说“为下文铺垫”的空衔接、
正文解释自己打算做什么、所有人物和资料都说同一种抽象话、没有新效果的
重复、没有模型依据的正文、没有写进成品的模型行，以及仍绑定旧稿的审查。

判断记录用 `judge_kind` 明说是 `independent_context` 还是 `self_review`。
自评通过也保留明确风险，不允许宽泛结论；质量未通过时仍须修复。
宽泛质量声明还要求完整的当前质量链、独立阅读、适用的原生研究/世界检查，
以及对仍然存活的竞争结论作出明确处置。`contested` 保留为研究风险，
“可以停止搜索”不会自动变成“可以断言”。

CompositionPlan 是唯一的单元树。长篇项目指向它并使用其单元 id；旅行用
一份 `trip_plan` 行程配合指南计划。`world_contract` / `world_refs` 绑定世界
引用，未被检查抓住的已知坏变体保持可见；`show_plan.py` 把计划放在当前文字
旁边读回。这些检查从实际文件推出边界和剩余工作，不接受手写最终结论。

然后每条路线再加自己的标准：调查和学术看证据与引用，小说看戏剧化、声音
和兑现，旅行看日期、能不能走、适不适合这个人、备选是否真的就在附近。

## 专业技能仍然各管各的

- ResearchGuard 的 `status` 提供问题级 `verdict`；`research_folder` 导入来源拥有的锚点，手写身份冲突会报错。
- SourceGuard 决定下一步搜什么、资料深度够不够。
- LogicGuard 负责资料保存、论证支持、结构、引文语义、模型深化和综合计划。
- TraceGuard 负责重要的时间、执行、因果、竞争叙事、反事实和预测边界。
- WorldGuard 负责事件、人物、空间、资源、能力、冲突、权力和规范能否一致。
- Documents 与 PDF 负责各自真实文件的修改、提取、渲染和视觉检查。

Logic Writing 可以组织和解释这些结果，但不能自己假装跑过专业检查，也不能
把缺失、部分通过或过期的结果改写成成功。

## 整体结构

```mermaid
flowchart TD
    U["用户请求"] --> R["按最终成品路由"]
    R --> I["investigation"]
    R --> A["academic-writing"]
    R --> F["fiction-writing"]
    R --> T["travel-guide"]
    I & A & F & T --> K["共享读者与成品内核"]
    K --> X["真正交付的成品"]
    X --> V["反向检查、新鲜度、最终路线闭环"]
    A -. "有限证据缺口" .-> I
    F -. "有限证据缺口" .-> I
    T -. "有限证据缺口" .-> I
```

共享内核不是第五条路线。兄弟路线不能互相当最终负责人；旅行使用中性的
读者投影，不会暗中调用小说路线。

更多边界见[架构说明](docs/architecture.md)、[责任地图](docs/responsibility-map.md)
和[迁移说明](MIGRATION.md)。

## 安装和使用

技能只用 `scripts/install_skill.py` 安装；`pip install .` 只登记项目元数据，不安装技能。

```text
python scripts/install_skill.py --target ~/.claude/skills      # 或 "$CODEX_HOME/skills"
python scripts/install_skill.py --target ~/.claude/skills --check
```

安装脚本把 `skills/logic-writing` 复制到 `<target>/logic-writing`（替换旧副本），
不复制只供本仓库测试使用的样例和回归脚本；`--check` 在已安装副本与源码不一致时返回 1。
ResearchGuard 和 WorldGuard 需要另外安装。

已经有计划的作品，先把计划读回来；第一行汇总绑定、审计、评审、收尾和没被抓住的已知坏改动：

```text
python skills/logic-writing/scripts/show_plan.py --input <folder>/reader-brief.json
```

然后调用：

```text
使用 $logic-writing，把这个请求路由到正确的最终负责人，并交付人能读懂的成品。
```

旧的 `storyline-design` 和 `travel-story-planner` 不提供兼容别名；
它们支持的需求现在统一从 `$logic-writing` 进入。

## 验证边界

每次推送和拉取请求都会运行 CI：全量 pytest、小说与旅行回归、`python -m flowguard map check`、
`python -m flowguard release`，以及安装文件的字节检查。第二个作业在声明的最低 ResearchGuard 版本上
运行测试、问题级 status 预检和三个成员预检。发布工作流只在同一源码提交的 CI 成功后发布。这些检查覆盖脚本和契约，
不证明某篇具体文字的质量；最终收尾仍须阅读实际成品。

## 不负责什么

Logic Writing 不能自动判定事实真伪、文学美感、原创性或旅行满意度。它也不是
日常文案、纯语法修改、快速查事实、通用诗歌或简单景点清单的万能入口。机器
检查到不了的地方，必须明确保留人工判断。

## 许可证

[MIT](LICENSE)

brief 请求中重复的正文内容和限制处置可从计划单元推出，小说单元的共享读者字段也可继承。显式填写的处置仍会检查，不自动推出刻意省略等不可见处置。
