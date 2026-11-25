# Contributing

欢迎改进真实业务行为、可靠性、评测和文档。先阅读 README 中的实现范围与指标口径，避免把模板代理分写成人类学习效果。

## Local workflow

```bash
python -m venv .venv
# Activate the environment for your shell.
python -m pip install -e '.[dev]'
python -m pytest -q
ruff check .
ruff format --check .
jewelmentor evaluate --output runtime/evaluation.json
python -m build
```

为行为变更加入能够复现问题的测试；故障测试使用真实 Store/Harness，仅替换外部模型或 HTTP 传输。新接口需要输入、错误与兼容性说明。修改数据库和 checkpoint 格式前先讨论迁移策略。

## Pull requests

1. 开 Issue 说明具体问题、预期行为和验收方法；小修复可直接提 PR。
2. 在 feature 分支提交聚焦的修改，使用 `feat:`、`fix:`、`docs:`、`test:`、`chore:` 等清晰前缀。
3. 记录实际验证命令与结果，不声称未运行的检查通过。
4. 语料修改注明来源与许可；评测数据修改需解释分母、版本及对指标的影响。
5. 不提交 API Key、企业内部资料、简历、真实客户对话或运行数据库。

安全问题请按 SECURITY.md 私下报告，不公开秘密。保持讨论具体、尊重贡献者，并清晰区分代码事实、测量结果与未来设想。
