"""Optional browser check: use system Python with Playwright and Chromium installed."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from openpyxl import load_workbook


def run():
    artifacts = Path(__file__).resolve().parents[1] / 'data'
    artifacts.mkdir(exist_ok=True)
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('http://127.0.0.1:8000', wait_until='networkidle')
        expect(page.locator('#empty')).to_be_visible()
        page.locator('#demo-toggle').check()
        expect(page.locator('#results tr')).to_have_count(8)
        page.screenshot(path=str(artifacts / 'desktop-demo.png'), full_page=True)
        page.locator('[data-platform="douyin"]').click()
        expect(page.locator('#results tr')).to_have_count(4)
        page.locator('[data-platform="all"]').click()
        page.locator('[data-view="search"]').click()
        page.locator('#keyword').fill('KPL')
        page.locator('#search-button').click()
        expect(page.locator('#results tr')).to_have_count(8)
        with page.expect_download() as download:
            page.locator('#export-button').click()
        path = artifacts / '热点素材-示例.xlsx'
        download.value.save_as(str(path))
        book = load_workbook(path)
        assert book['热点素材'].max_row == 9
        assert '示例' in book['采集说明']['B1'].value
        page.locator('[data-view="settings"]').click()
        expect(page.locator('.source-card')).to_have_count(2)
        page.locator('#demo-toggle').uncheck()
        page.locator('[data-view="daily"]').click()
        expect(page.locator('#results tr')).to_have_count(0)
        expect(page.locator('#demo-banner')).to_be_hidden()
        page.set_viewport_size({'width': 390, 'height': 844})
        page.screenshot(path=str(artifacts / 'mobile-real.png'), full_page=True)
        assert page.evaluate('() => document.documentElement.scrollWidth <= window.innerWidth')
        browser.close()
    assert not errors, errors
    print('PASS: demo/real isolation, filtering, search, Excel download, settings, mobile layout, no JS errors')


if __name__ == '__main__':
    run()
