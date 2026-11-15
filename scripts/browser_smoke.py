"""Real Chromium UI journey. Requires running local services; resets synthetic demo state."""

import json, os, shutil
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = os.getenv("SMOKE_URL", "http://127.0.0.1:3001")
OUT = Path("artifacts")
OUT.mkdir(exist_ok=True)
with sync_playwright() as p:
    chrome = shutil.which("google-chrome")
    browser = p.chromium.launch(
        headless=True, executable_path=chrome, args=["--no-sandbox"]
    )
    page = browser.new_page(
        viewport={"width": 1920, "height": 1080}, device_scale_factor=1
    )
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    # Reset is local-only and recreates the same synthetic scenario.
    response = page.request.post(BASE + "/api/demo/reset")
    assert response.ok, response.text()
    page.goto(BASE, wait_until="networkidle")
    expect(
        page.get_by_role("heading", name="Campaign confidence starts here.")
    ).to_be_visible()
    page.screenshot(path=str(OUT / "overview-1920.png"), full_page=True)
    for title, path in [
        ("Campaigns", "/campaigns"),
        ("AI Audit Center", "/audit"),
        ("Remediation", "/remediation"),
        ("Governance", "/governance"),
        ("Audit History", "/history"),
        ("Integrations", "/integrations"),
    ]:
        page.locator("nav").get_by_role("link", name=title, exact=True).click()
        expect(page).to_have_url(BASE + path)
        expect(page.locator("main")).to_be_visible()
    expect(page.get_by_text("Salesforce Not Connected", exact=True)).to_be_visible()
    page.locator("nav").get_by_role("link", name="Live Demo", exact=True).click()
    expect(page.get_by_role("heading", name="When AI Audits AI.")).to_be_visible()
    expect(page.get_by_text("100 synthetic contacts", exact=True)).to_be_visible()
    page.get_by_role("button", name="Run Audit", exact=True).click()
    expect(
        page.get_by_text("Opted-out contacts in audience", exact=True)
    ).to_be_visible(timeout=15000)
    expect(page.get_by_text("Missing consent in audience", exact=True)).to_be_visible()
    expect(
        page.get_by_text("Unsupported marketing guarantee", exact=True)
    ).to_be_visible()
    expect(page.get_by_text("AR language variant missing", exact=True)).to_be_visible()
    expect(page.locator(".risk-ring.large strong")).to_have_text("100")
    page.screenshot(path=str(OUT / "demo-findings-1920.png"), full_page=True)
    page.get_by_role("button", name="Generate Corrections", exact=True).first.click()
    expect(
        page.get_by_text("Exclude 30 ineligible recipients", exact=True)
    ).to_be_visible()
    # Individual rejection/acceptance is persisted through API and survives rerender.
    audience = (
        page.locator(".correction")
        .filter(has_text="Exclude 30 ineligible recipients")
        .get_by_role("checkbox")
    )
    audience.uncheck()
    expect(audience).not_to_be_checked()
    page.wait_for_timeout(400)
    audience.check()
    expect(audience).to_be_checked()
    page.wait_for_timeout(400)
    page.get_by_role("button", name="Apply Selected Corrections", exact=True).click()
    expect(page.get_by_text("70 synthetic contacts", exact=True)).to_be_visible()
    page.get_by_role("button", name="Re-Audit Draft", exact=True).click()
    expect(page.locator(".risk-ring.large strong")).to_have_text("0", timeout=15000)
    expect(
        page.get_by_text("No policy findings in this audited version.", exact=True)
    ).to_be_visible()
    page.get_by_role("button", name="Request Approval", exact=True).click()
    page.get_by_role("button", name="Approve", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("textbox", name="Reviewer · simulated local identity").fill(
        "Synthetic QA Reviewer"
    )
    dialog.get_by_role("textbox", name="Decision comments").fill(
        "Reviewed corrected copy, audience exclusions, and language variant."
    )
    dialog.get_by_role("checkbox").check()
    dialog.get_by_role("button", name="Approve", exact=True).click()
    expect(
        page.get_by_role("heading", name="Campaign Approved for Activation", exact=True)
    ).to_be_visible()
    expect(page.get_by_text("No messages have been sent.", exact=True)).to_be_visible()
    page.get_by_role("button", name="View Audit Trail", exact=True).click()
    expect(
        page.locator("#demo-trail").get_by_text("human approved", exact=True)
    ).to_be_visible()
    page.reload(wait_until="networkidle")
    expect(
        page.get_by_role("heading", name="Campaign Approved for Activation", exact=True)
    ).to_be_visible()
    page.screenshot(path=str(OUT / "demo-approved-1920.png"), full_page=True)
    # Campaign creation, search, editing and audience selection through actual UI.
    page.locator("nav").get_by_role("link", name="Campaigns", exact=True).click()
    page.get_by_role("button", name="Create Campaign", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("textbox", name="Campaign name", exact=True).fill(
        "Synthetic Browser QA"
    )
    dialog.get_by_role("textbox", name="Email subject", exact=True).fill(
        "Your next workshop"
    )
    dialog.get_by_role("textbox", name="Campaign content", exact=True).fill(
        "Explore our practical workshops and registration details."
    )
    dialog.get_by_role("button", name="Select eligible", exact=True).click()
    dialog.get_by_role("button", name="Save Campaign", exact=True).click()
    page.get_by_role("textbox", name="Search campaigns").fill("Synthetic Browser QA")
    expect(page.locator("tbody tr")).to_have_count(1)
    page.get_by_role("button", name="Edit Synthetic Browser QA", exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("textbox", name="Campaign name", exact=True).fill(
        "Synthetic Browser QA Updated"
    )
    dialog.get_by_role("button", name="Save Campaign", exact=True).click()
    expect(
        page.get_by_role("button", name="Open Synthetic Browser QA Updated", exact=True)
    ).to_be_visible()
    # Restore synthetic original for the presenter, then verify responsive dashboard.
    page.locator("nav").get_by_role("link", name="Live Demo", exact=True).click()
    page.get_by_role("button", name="Reset Demo", exact=True).click()
    page.get_by_role("dialog").get_by_role(
        "button", name="Reset Demo", exact=True
    ).click()
    expect(page.get_by_text("100 synthetic contacts", exact=True)).to_be_visible()
    expect(page.locator(".risk-ring.large strong")).to_have_text("—")
    page.goto(BASE, wait_until="networkidle")
    page.set_viewport_size({"width": 390, "height": 844})
    page.screenshot(path=str(OUT / "overview-mobile.png"), full_page=True)
    assert page.evaluate(
        "document.documentElement.scrollWidth <= window.innerWidth"
    ), "Horizontal page overflow"
    assert not errors, errors
    browser.close()
    result = {
        "result": "passed",
        "journey": [
            "dashboard",
            "all navigation",
            "honest integration status",
            "audit",
            "four dynamic findings",
            "individual correction selection",
            "apply",
            "70 recipients",
            "reaudit risk 0",
            "human approval",
            "persistent reload",
            "audit trail",
            "campaign create/search/edit",
            "reset",
            "390px responsive viewport",
        ],
        "browser_errors": errors,
        "screenshots": str(OUT),
    }
    (OUT / "browser-results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
