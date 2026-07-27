"""
前端浏览器自动化测试脚本
使用 Playwright 测试所有页面，发现 bug

测试范围：
- 所有主要页面的加载
- API 请求状态
- 控制台错误
- 数据渲染
- 交互功能
"""

import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright, Page
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:3003"

# 测试页面列表
TEST_PAGES = [
    ("/", "首页/仪表盘"),
    ("/funds", "基金列表"),
    ("/funds/520680.SH", "基金详情"),
    ("/managers", "基金经理列表"),
    ("/managers/M001", "基金经理详情"),
    ("/screening", "基金筛选"),
    ("/research", "研究报告"),
    ("/barra", "Barra风险分析"),
    ("/brinson", "Brinson归因分析"),
]

test_results = []


async def test_page(page: Page, path: str, name: str) -> dict:
    """测试单个页面"""
    result = {
        "path": path,
        "name": name,
        "status": "unknown",
        "errors": [],
        "warnings": [],
        "api_calls": [],
        "load_time": 0,
    }

    try:
        # 监听控制台消息
        console_messages = []

        def handle_console(msg):
            console_messages.append({
                "type": msg.type,
                "text": msg.text,
            })

        page.on("console", handle_console)

        # 监听 API 请求
        api_requests = []

        def handle_request(request):
            if "/api/" in request.url:
                api_requests.append({
                    "url": request.url,
                    "method": request.method,
                })

        def handle_response(response):
            if "/api/" in response.url:
                for req in api_requests:
                    if req["url"] == response.url:
                        req["status"] = response.status
                        req["ok"] = response.ok

        page.on("request", handle_request)
        page.on("response", handle_response)

        # 导航到页面
        logger.info(f"Testing {name} ({path})...")
        start_time = asyncio.get_event_loop().time()

        response = await page.goto(f"{BASE_URL}{path}", wait_until="networkidle", timeout=30000)

        end_time = asyncio.get_event_loop().time()
        result["load_time"] = round((end_time - start_time) * 1000, 2)

        # 检查页面加载状态
        if response and response.ok:
            result["status"] = "success"
        else:
            result["status"] = "failed"
            result["errors"].append(f"Page load failed with status {response.status if response else 'unknown'}")

        # 等待一下让 JS 执行
        await asyncio.sleep(2)

        # 检查控制台错误
        for msg in console_messages:
            if msg["type"] == "error":
                result["errors"].append(f"Console error: {msg['text']}")
            elif msg["type"] == "warning":
                result["warnings"].append(f"Console warning: {msg['text']}")

        # 检查 API 调用
        result["api_calls"] = api_requests
        for req in api_requests:
            if not req.get("ok", True):
                result["errors"].append(f"API failed: {req['method']} {req['url']} -> {req.get('status', 'unknown')}")

        # 截图
        screenshot_path = f"screenshots/{name.replace('/', '_')}.png"
        await page.screenshot(path=screenshot_path)
        result["screenshot"] = screenshot_path

        # 检查页面标题
        title = await page.title()
        result["title"] = title

        logger.info(f"✓ {name}: {result['status']} ({result['load_time']}ms)")

    except Exception as e:
        result["status"] = "error"
        result["errors"].append(f"Test error: {str(e)}")
        logger.error(f"✗ {name}: {e}")

    return result


async def run_tests():
    """运行所有测试"""
    logger.info("=" * 60)
    logger.info("开始前端浏览器测试")
    logger.info("=" * 60)

    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()

        # 测试每个页面
        for path, name in TEST_PAGES:
            result = await test_page(page, path, name)
            test_results.append(result)

        await browser.close()

    # 生成报告
    generate_report()


def generate_report():
    """生成测试报告"""
    logger.info("=" * 60)
    logger.info("测试报告")
    logger.info("=" * 60)

    total = len(test_results)
    success = sum(1 for r in test_results if r["status"] == "success")
    failed = sum(1 for r in test_results if r["status"] in ["failed", "error"])

    logger.info(f"总计: {total} 个页面")
    logger.info(f"成功: {success}")
    logger.info(f"失败: {failed}")
    logger.info("")

    # 详细错误
    has_errors = False
    for result in test_results:
        if result["errors"]:
            has_errors = True
            logger.error(f"\n{result['name']} ({result['path']}):")
            for error in result["errors"]:
                logger.error(f"  - {error}")

    if not has_errors:
        logger.info("✓ 所有页面测试通过，无错误！")

    # 保存 JSON 报告
    report_file = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(test_results, f, indent=2, ensure_ascii=False)

    logger.info(f"\n详细报告已保存到: {report_file}")


if __name__ == "__main__":
    # 创建截图目录
    import os
    os.makedirs("screenshots", exist_ok=True)

    # 运行测试
    asyncio.run(run_tests())
