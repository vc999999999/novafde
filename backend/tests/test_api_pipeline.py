from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import yaml
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


def build_draft_payload() -> dict:
    return {
        "displayName": "Product Research",
        "name": "product-research",
        "language": "zh-CN",
        "skillType": "workflow",
        "targetPlatforms": ["claude-code", "codex", "hermes-openclaw"],
        "trigger": {
            "intent": "帮助产品团队系统化完成竞品调研",
            "taskType": "research-workflow",
            "positiveExamples": ["竞品调研", "市场机会扫描"],
            "negativeExamples": ["写前端组件", "修复数据库迁移"],
            "commonPhrases": ["帮我做竞品调研", "把这份市场笔记整理成研究流程"],
            "relatedFileTypes": ["md", "csv"],
            "relatedTools": ["web-search", "spreadsheet"],
            "relatedObjects": ["竞品", "市场信号"],
        },
        "workflow": {
            "objective": "把零散市场信息转成可验证的产品研究结论",
            "preconditions": "用户提供产品领域或初始市场假设",
            "steps": [
                {
                    "id": "step_1",
                    "purpose": "明确研究边界",
                    "action": "询问产品领域、目标用户和关键问题",
                    "input": "用户的初始研究目标",
                    "output": "结构化研究计划",
                    "validation": "计划覆盖目标用户、竞品范围和关键指标",
                    "failureHandling": "如果范围太宽，要求用户先选择一个细分市场",
                },
                {
                    "id": "step_2",
                    "purpose": "沉淀证据",
                    "action": "整理来源、指标和可疑假设",
                    "input": "研究计划和材料",
                    "output": "带来源的证据表",
                    "validation": "每个结论至少有一个来源或明确标记为假设",
                    "failureHandling": "如果来源不足，输出缺口清单而不是编造结论",
                },
            ],
        },
        "context": {
            "filesToRead": ["references/research-methods.md"],
            "needsReferences": True,
            "needsScripts": False,
            "needsAssets": True,
            "loadingRule": "优先读取 references 下与研究方法相关的文件",
        },
        "knowledge": {
            "industryRules": ["区分事实、推断和假设"],
            "internalProcesses": ["先定义研究问题，再收集材料"],
            "personalExperience": ["结论要能回溯到具体证据"],
            "pitfalls": [
                {
                    "id": "pit_1",
                    "description": "把营销话术当成事实",
                    "goodExample": "标记为供应商自述，并寻找第三方来源",
                    "badExample": "直接把官网 claim 写成市场结论",
                }
            ],
        },
        "outputControl": {
            "freedom": "medium",
            "allowHardLimits": True,
            "validationStrictness": "normal",
            "generateInstallGuide": True,
            "allowDownloadWithWarnings": False,
        },
        "supplement": {
            "messages": [
                {
                    "id": "msg_1",
                    "role": "user",
                    "content": "需要支持 Claude Code、Codex、Hermes/OpenClaw 三端安装说明。",
                    "timestamp": 1780915200000,
                }
            ]
        },
    }


def make_client(tmp_path: Path) -> TestClient:
    app = create_app(Settings(data_dir=tmp_path))
    return TestClient(app)


def create_generation_provider(client: TestClient) -> dict:
    response = client.post(
        "/api/model-providers",
        json={
            "name": "claude-primary",
            "protocol": "claude",
            "baseUrl": "https://api.example.test",
            "apiKeyRef": {"type": "env", "name": "SKILLFORGE_TEST_API_KEY"},
            "defaultModel": "test-model",
            "roles": ["generation", "repair", "validation-explanation"],
            "timeoutMs": 120000,
            "retries": 2,
            "streaming": True,
            "customHeaders": {},
            "enabled": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_generation_pipeline_builds_valid_skill_package(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    create_generation_provider(client)

    draft_response = client.post("/api/drafts", json=build_draft_payload())
    assert draft_response.status_code == 201
    draft = draft_response.json()
    assert draft["id"].startswith("draft_")
    assert draft["name"] == "product-research"

    generation_response = client.post(f"/api/drafts/{draft['id']}/generate")
    assert generation_response.status_code == 201
    generation = generation_response.json()
    assert generation["status"] == "success"
    assert generation["currentStage"] == "packaging"
    assert generation["progress"] == 100
    assert generation["blockingIssues"] == 0
    assert generation["downloadInfo"]["packageName"] == "product-research-package.zip"
    assert generation["downloadInfo"]["fileCount"] >= 5

    preview_response = client.get(f"/api/generations/{generation['id']}/preview")
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert "SKILL.md" in preview["skillMd"]
    assert preview["files"][0]["name"] == "product-research"

    validation_response = client.get(f"/api/generations/{generation['id']}/validation")
    assert validation_response.status_code == 200
    validation = validation_response.json()
    assert validation["blockingIssues"] == 0
    assert any(item["ruleId"] == "PKG-001" and item["level"] == "pass" for item in validation["items"])

    download_response = client.get(f"/api/generations/{generation['id']}/download")
    assert download_response.status_code == 200
    assert download_response.headers["content-type"] == "application/zip"

    with ZipFile(BytesIO(download_response.content)) as zip_file:
        names = zip_file.namelist()
        assert "product-research/SKILL.md" in names
        assert "install/claude-code.md" in names
        assert "install/codex.md" in names
        assert "install/hermes-openclaw.md" in names
        assert "validation-report.json" in names
        assert "package-manifest.json" in names
        assert all(not name.startswith("/") and ".." not in Path(name).parts for name in names)

        skill_md = zip_file.read("product-research/SKILL.md").decode("utf-8")
        frontmatter_text = skill_md.split("---", 2)[1]
        frontmatter = yaml.safe_load(frontmatter_text)
        assert frontmatter == {
            "name": "product-research",
            "description": frontmatter["description"],
        }
        assert frontmatter["description"].startswith("Use when")


def test_generate_returns_blocking_validation_for_incomplete_draft(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    create_generation_provider(client)
    payload = build_draft_payload()
    payload["name"] = ""
    payload["trigger"]["intent"] = ""
    payload["workflow"]["steps"] = []

    draft_response = client.post("/api/drafts", json=payload)
    assert draft_response.status_code == 201
    draft = draft_response.json()
    assert draft["name"] == "product-research"

    generation_response = client.post(f"/api/drafts/{draft['id']}/generate")
    assert generation_response.status_code == 201
    generation = generation_response.json()
    assert generation["status"] == "failed"
    assert generation["blockingIssues"] >= 2
    assert generation["downloadInfo"] is None
    assert generation["errorMessage"] == "生成输入存在阻塞问题，请补充草稿后重试。"

    issue_rule_ids = {item["ruleId"] for item in generation["validation"]}
    assert {"BRIEF-001", "WF-001"}.issubset(issue_rule_ids)
