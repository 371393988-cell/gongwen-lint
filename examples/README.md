# 合成示例

本目录中的内容均为人工编写的虚构材料，不对应任何真实机关、人员、项目或业务。

在仓库根目录执行：

```bash
python -m gongwen_lint examples/synthetic_clean.txt --fail-level warning
python -m gongwen_lint examples/synthetic_issues.txt --fail-level never
```

第一个示例用于展示无已知问题时的输出；第二个示例故意包含套话、回避式表态、
占位符和连续标点，用于展示规则编号与修改建议。示例只验证文字规则，不代替 DOCX
版面检查。
