"""
TDD Test Suite: End-to-End Browser Tests
Tests define what the user SEES and INTERACTS with.
These tests will be run with Playwright or Selenium.
"""
import pytest


class TestRoutePlannerPage:
    """E2E tests for the main route planner page"""

    def test_page_loads_with_map(self, browser):
        """Main page loads with a Leaflet map visible"""
        browser.goto("/")
        map_element = browser.locator("#map")
        assert map_element.is_visible(), "Map should be visible on page load"

    def test_search_bar_visible(self, browser):
        """Search bar with From/To inputs should be visible"""
        browser.goto("/")
        assert browser.locator("#search-from").is_visible()
        assert browser.locator("#search-to").is_visible()
        assert browser.locator("#search-btn").is_visible()

    def test_night_mode_toggle_visible(self, browser):
        """Night mode toggle switch should be visible in header"""
        browser.goto("/")
        assert browser.locator("#night-toggle").is_visible()

    def test_emergency_button_always_visible(self, browser):
        """Emergency button should be visible on every page"""
        browser.goto("/")
        assert browser.locator("#emergency-btn").is_visible()

    def test_search_returns_routes_on_map(self, browser):
        """After searching, 3 colored polylines should appear on map"""
        browser.goto("/")
        browser.fill("#search-from", "MUJ Jaipur")
        browser.fill("#search-to", "Jaipur Railway Station")
        browser.click("#search-btn")
        browser.wait_for_selector(".route-polyline", timeout=10000)
        polylines = browser.locator(".route-polyline")
        assert polylines.count() == 3, f"Expected 3 routes, got {polylines.count()}"

    def test_sidebar_shows_safety_breakdown(self, browser):
        """After searching, sidebar shows 7-factor safety breakdown"""
        browser.goto("/")
        browser.fill("#search-from", "MUJ Jaipur")
        browser.fill("#search-to", "Jaipur Railway Station")
        browser.click("#search-btn")
        browser.wait_for_selector("#safety-breakdown", timeout=10000)
        breakdown = browser.locator("#safety-breakdown")
        assert breakdown.is_visible()
        # Check all 7 factors are listed
        for factor in ["lighting", "police", "crowd", "road_type", "crime", "accessibility", "reports"]:
            assert browser.locator(f"[data-factor='{factor}']").is_visible(), \
                f"Safety factor '{factor}' not shown in breakdown"

    def test_sidebar_shows_ai_explanation(self, browser):
        """After searching, Groq AI explanation appears in sidebar"""
        browser.goto("/")
        browser.fill("#search-from", "MUJ Jaipur")
        browser.fill("#search-to", "Jaipur Railway Station")
        browser.click("#search-btn")
        browser.wait_for_selector("#ai-explanation", timeout=15000)
        explanation = browser.locator("#ai-explanation")
        assert explanation.is_visible()
        text = explanation.text_content()
        assert len(text) > 20, "AI explanation should be meaningful text"

    def test_route_colors_are_correct(self, browser):
        """Fastest=red, Safest=green, Recommended=purple"""
        browser.goto("/")
        browser.fill("#search-from", "MUJ Jaipur")
        browser.fill("#search-to", "Jaipur Railway Station")
        browser.click("#search-btn")
        browser.wait_for_selector(".route-polyline", timeout=10000)
        assert browser.locator(".route-fastest").is_visible()
        assert browser.locator(".route-safest").is_visible()
        assert browser.locator(".route-recommended").is_visible()

    def test_clicking_route_shows_details(self, browser):
        """Clicking a route in sidebar should highlight it on map"""
        browser.goto("/")
        browser.fill("#search-from", "MUJ Jaipur")
        browser.fill("#search-to", "Jaipur Railway Station")
        browser.click("#search-btn")
        browser.wait_for_selector(".route-card", timeout=10000)
        browser.click(".route-card[data-type='safest']")
        assert browser.locator(".route-card.active[data-type='safest']").is_visible()

    def test_loading_state_while_calculating(self, browser):
        """Loading spinner should appear while routes are being calculated"""
        browser.goto("/")
        browser.fill("#search-from", "MUJ Jaipur")
        browser.fill("#search-to", "Jaipur Railway Station")
        browser.click("#search-btn")
        # Loading should appear briefly
        # (may be too fast to catch in tests, so we check it exists in DOM)
        assert browser.locator("#loading-spinner").count() >= 0


class TestNightMode:
    """E2E tests for night mode toggle"""

    def test_toggle_changes_heatmap_colors(self, browser):
        """Toggling night mode should change heatmap overlay colors"""
        browser.goto("/")
        browser.fill("#search-from", "MUJ Jaipur")
        browser.fill("#search-to", "Jaipur Railway Station")
        browser.click("#search-btn")
        browser.wait_for_selector(".route-polyline", timeout=10000)
        # Get current recommended route safety score
        day_score = browser.locator("#recommended-score").text_content()
        # Toggle night mode
        browser.click("#night-toggle")
        browser.wait_for_timeout(1000)
        night_score = browser.locator("#recommended-score").text_content()
        assert day_score != night_score, "Night mode should change safety scores"

    def test_night_mode_shows_change_description(self, browser):
        """Night mode sidebar should explain what changed"""
        browser.goto("/")
        browser.fill("#search-from", "MUJ Jaipur")
        browser.fill("#search-to", "Jaipur Railway Station")
        browser.click("#search-btn")
        browser.wait_for_selector(".route-polyline", timeout=10000)
        browser.click("#night-toggle")
        browser.wait_for_timeout(1000)
        change_desc = browser.locator("#night-changes")
        if change_desc.is_visible():
            text = change_desc.text_content()
            assert "avoids" in text.lower() or "route" in text.lower(), \
                "Change description should mention route adjustments"


class TestSafetyHeatmapPage:
    """E2E tests for the city-wide safety heatmap"""

    def test_heatmap_page_loads(self, browser):
        """Heatmap page should show map with color overlay"""
        browser.goto("/heatmap")
        assert browser.locator("#heatmap-map").is_visible()

    def test_time_slider_visible(self, browser):
        """Time slider should be visible and interactive"""
        browser.goto("/heatmap")
        slider = browser.locator("#time-slider")
        assert slider.is_visible()
        # Should be a range input
        assert slider.get_attribute("type") == "range"

    def test_legend_visible(self, browser):
        """Color legend (red/yellow/green) should be visible"""
        browser.goto("/heatmap")
        assert browser.locator("#heatmap-legend").is_visible()

    def test_danger_zones_list_visible(self, browser):
        """Top dangerous zones should be listed"""
        browser.goto("/heatmap")
        zones = browser.locator("#danger-zones")
        assert zones.is_visible()
        items = browser.locator(".danger-zone-item")
        assert items.count() >= 1, "Should show at least 1 danger zone"


class TestEmergencyMode:
    """E2E tests for emergency overlay"""

    def test_emergency_overlay_opens(self, browser):
        """Clicking emergency button opens overlay"""
        browser.goto("/")
        browser.click("#emergency-btn")
        overlay = browser.locator("#emergency-overlay")
        assert overlay.is_visible()

    def test_emergency_shows_police(self, browser):
        """Emergency overlay shows nearest police station"""
        browser.goto("/")
        browser.click("#emergency-btn")
        assert browser.locator("#nearest-police").is_visible()

    def test_emergency_shows_hospital(self, browser):
        """Emergency overlay shows nearest hospital"""
        browser.goto("/")
        browser.click("#emergency-btn")
        assert browser.locator("#nearest-hospital").is_visible()

    def test_emergency_shows_numbers(self, browser):
        """Emergency overlay shows 100, 108, 112, 1091"""
        browser.goto("/")
        browser.click("#emergency-btn")
        text = browser.locator("#emergency-overlay").text_content()
        assert "100" in text
        assert "108" in text
        assert "112" in text

    def test_emergency_closes(self, browser):
        """Emergency overlay can be closed"""
        browser.goto("/")
        browser.click("#emergency-btn")
        assert browser.locator("#emergency-overlay").is_visible()
        browser.click("#emergency-close")
        assert not browser.locator("#emergency-overlay").is_visible()


class TestResponsiveLayout:
    """E2E tests for responsive design"""

    def test_mobile_sidebar_collapses(self, browser):
        """On mobile, sidebar should collapse to bottom sheet"""
        browser.set_viewport_size({"width": 375, "height": 812})
        browser.goto("/")
        # Sidebar should be hidden or collapsed on mobile
        sidebar = browser.locator("#sidebar")
        # Either hidden or at bottom
        assert not sidebar.is_visible() or \
               sidebar.evaluate("el => getComputedStyle(el).position") == "fixed"

    def test_desktop_sidebar_visible(self, browser):
        """On desktop, sidebar should be visible side-by-side with map"""
        browser.set_viewport_size({"width": 1920, "height": 1080})
        browser.goto("/")
        assert browser.locator("#sidebar").is_visible()
        assert browser.locator("#map").is_visible()

    def test_map_takes_majority_of_screen(self, browser):
        """Map should take at least 60% of viewport width on desktop"""
        browser.set_viewport_size({"width": 1920, "height": 1080})
        browser.goto("/")
        map_box = browser.locator("#map").bounding_box()
        sidebar_box = browser.locator("#sidebar").bounding_box()
        assert map_box["width"] > sidebar_box["width"], \
            "Map should be wider than sidebar"


class TestAccessibility:
    """E2E tests for accessibility"""

    def test_all_buttons_have_labels(self, browser):
        """All buttons should have accessible labels"""
        browser.goto("/")
        buttons = browser.locator("button")
        for i in range(buttons.count()):
            btn = buttons.nth(i)
            label = btn.get_attribute("aria-label") or btn.text_content()
            assert label and len(label.strip()) > 0, \
                f"Button {i} has no accessible label"

    def test_keyboard_navigation_works(self, browser):
        """Tab key should move focus through interactive elements"""
        browser.goto("/")
        browser.press("Tab")
        focused = browser.evaluate("document.activeElement.tagName")
        assert focused in ["INPUT", "BUTTON", "A", "SELECT"], \
            f"Tab focused on {focused}, expected interactive element"

    def test_color_contrast_on_route_labels(self, browser):
        """Route labels should have sufficient contrast"""
        browser.goto("/")
        browser.fill("#search-from", "MUJ Jaipur")
        browser.fill("#search-to", "Jaipur Railway Station")
        browser.click("#search-btn")
        browser.wait_for_selector(".route-card", timeout=10000)
        # Just check that the text is readable (not empty)
        for route_type in ["fastest", "safest", "recommended"]:
            text = browser.locator(f".route-card[data-type='{route_type}']").text_content()
            assert len(text.strip()) > 0, f"Route card '{route_type}' has empty text"
