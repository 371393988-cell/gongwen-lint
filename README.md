# gongwen-lint（公文校对工具）

[![tests](https://github.com/371393988-cell/gongwen-lint/actions/workflows/tests.yml/badge.svg)](https://github.com/371393988-cell/gongwen-lint/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一个本地运行、规则透明、默认只读的中文公文校对命令行工具。

`gongwen-lint` 用于在人工复核前发现可机械识别的问题，支持 `.txt`、`.md`
和 `.docx` 文件。格式规则以 **GB/T 9704—2012《党政机关公文格式》** 为
基础，首个版本重点检查：

- “晴雨表”“压舱石”“指南针”等缺乏针对性的套话；
- “铁军”“新兵”等不适合一般政府机关语境的军事化表达；
- “不一定”“不等于”“不能保证”等回避式表态；
- `TODO`、“待补充”“某某”等未清理占位符；
- 连续标点、中文后的半角标点和超长句；
- DOCX 中仍使用名称含 `2312` 的旧字体；
- 可选检查 DOCX 是否显式使用名称含 `_GBK` 的字体。
- DOCX 是否为 A4 纵向纸张，上白边是否为 37 mm±1 mm，左白边是否为
  28 mm±1 mm，版心是否为 156 mm×225 mm；
- 正文样式是否一般采用3号字（16 pt）；
- 发文字号年份括号、顺序号、结构层次序数、附件说明和成文日期数字格式。

工具不会修改原文件，也不会上传文档。规则、位置和修改建议均写入 JSON 或
Markdown 报告，便于复核和持续改进。

> 本项目是辅助校对工具，不代替发文机关的政治审核、合法性审核、保密审查和
> 人工文字审核，也不声称代表任何机关的正式规范。

## 安装与使用

需要 Python 3.10 或更高版本，无第三方运行时依赖。

```bash
python -m pip install -e .
gongwen-lint ./example.docx --json result.json --markdown result.md
```

递归检查一个目录：

```bash
gongwen-lint ./documents --require-gbk-font
```

DOCX 版面检查默认启用。仅检查文字、不检查页面设置时可使用
`--no-layout-check`。`--require-gbk-font` 是面向采用方正 `_GBK` 字体规范的
机构配置；GB/T 9704—2012 本身规定的是字体类别和字号，并未指定某一厂商字体。

只在发现错误级问题时返回非零退出码：

```bash
gongwen-lint ./documents --fail-level error
```

`--fail-level` 可选 `warning`、`error` 或 `never`。默认值为 `warning`，适合在
持续集成中阻止带有未复核问题的文稿进入下一环节。

## 报告示例

```text
example.docx:12:8 [warning] wording.cliche
“压舱石”属于高频套话，请改为与具体职责、措施或效果直接对应的表述。
```

每条结果包含文件、行或段落、列、严重程度、规则编号、命中的文本和修改建议。
JSON 结构在同一主版本内保持向后兼容。

仓库提供完全由人工编写的[合成示例](examples/README.md)，可用于快速试运行，
其中不含任何真实机关名称、人员信息、业务数据或本地文稿。

## 设计原则

- **本地优先**：不联网、不上传原文。
- **只读默认**：只报告问题，不自动改写文件。
- **规则可解释**：每项结果都能对应到明确规则。
- **审慎提示**：无法可靠机械判断的内容交由人工复核。
- **可测试**：规则通过合成文本和最小 DOCX 样例验证。

## 自动检查与人工复核边界

程序可以从 DOCX 结构中可靠读取纸张尺寸、页边、版心、部分样式和正文文本。
以下事项受 Word 实际分页、视觉排列或印制过程影响，当前版本只在文档中提示人工
复核，不宣称自动判定合格：

- 一般每面22行、每行28字并撑满版心；
- 标题换行是否词意完整，以及梯形或菱形排列是否协调；
- 红色分隔线、印章、签名章、版记和页码的精确视觉位置；
- 双面印刷、油墨、裁切和装订质量；
- 特定格式公文和本单位补充规范中的特殊调整。

本仓库不转载标准 PDF 或用户文稿。规则实现仅记录必要的标准编号、参数、检查
逻辑和简要说明。

## 路线图

版本目标、验收标准和保密边界见 [ROADMAP.md](ROADMAP.md)。路线图只使用公开
规范和合成材料，不以真实机关文稿作为公开测试数据。

参与开发请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。安全与隐私说明见
[SECURITY.md](SECURITY.md)。

## License

[MIT](LICENSE)
