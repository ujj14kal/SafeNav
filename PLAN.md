# SafeRoute — Safe Route Recommendation System
## Complete Project Plan (TDD Approach)

**Hackathon:** IIC 3.0 — International Innovation Challenge
**Theme:** Women & Child Safety
**PS:** #22 — Safe Route Recommendation System
**Duration:** 36 hours
**Tech Stack:** Flask + Leaflet.js + Tailwind CSS + Groq AI

---

## PHASE 0: PROJECT ARCHITECTURE

```
SafeRoute/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration (dev/prod/test)
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── api.py               # REST API endpoints
│   │   └── views.py             # Page routes (serve HTML)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── safety_engine.py     # Safety scoring algorithm
│   │   ├── route_optimizer.py   # Dijkstra + Pareto optimization
│   │   ├── heatmap.py           # Heatmap data generator
│   │   ├── poi_service.py       # POI data (police, hospitals, etc.)
│   │   ├── groq_service.py      # Groq AI explanations
│   │   ├── community.py         # Incident reporting system
│   │   └── emergency.py         # Emergency nearest-point finder
│   ├── models/
│   │   ├── __init__.py
│   │   ├── graph.py             # NetworkX road network
│   │   ├── safety_score.py      # Safety score data model
│   │   ├── route.py             # Route data model
│   │   └── report.py            # Community report model
│   ├── data/
│   │   ├── jaipur_graph.pkl     # Pre-built road network
│   │   ├── safety_scores.json   # Pre-computed safety scores
│   │   ├── pois.json            # Police, hospitals, shops
│   │   └── crime_data.json      # NCRB crime statistics
│   └── utils/
│       ├── __init__.py
│       ├── geo.py               # Geographic calculations
│       ├── time_utils.py        # Time-based adjustments
│       └── validators.py        # Input validation
├── static/
│   ├── css/
│   │   └── style.css            # Tailwind + custom styles
│   ├── js/
│   │   ├── app.js               # Main app logic
│   │   ├── map.js               # Leaflet map initialization
│   │   ├── routes.js            # Route rendering (polylines)
│   │   ├── heatmap.js           # Heatmap layer
│   │   ├── markers.js           # POI markers
│   │   ├── search.js            # Location search
│   │   ├── nightmode.js         # Night mode toggle
│   │   ├── emergency.js         # Emergency panel
│   │   └── community.js         # Report submission
│   └── img/
│       └── icons/               # Map markers, logo
├── templates/
│   ├── base.html                # Base layout (nav, footer)
│   ├── index.html               # Main route planner
│   ├── heatmap.html             # City-wide safety heatmap
│   ├── school.html              # School route mode
│   ├── emergency.html           # Emergency mode
│   ├── admin.html               # City admin dashboard
│   └── components/
│       ├── sidebar.html         # Route details sidebar
│       ├── search_bar.html      # Search input
│       └── modal.html           # Report/modal dialogs
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Pytest fixtures
│   ├── test_safety_engine.py    # Safety scoring unit tests
│   ├── test_route_optimizer.py  # Routing algorithm tests
│   ├── test_poi_service.py      # POI data tests
│   ├── test_groq_service.py     # AI explanation tests
│   ├── test_community.py        # Reporting system tests
│   ├── test_emergency.py        # Emergency feature tests
│   ├── test_api.py              # API endpoint integration tests
│   ├── test_e2e.py              # End-to-end browser tests
│   └── fixtures/
│       ├── sample_graph.json    # Test road network
│       ├── sample_pois.json     # Test POI data
│       └── sample_scores.json   # Test safety scores
├── scripts/
│   ├── download_osm.py          # Download Jaipur OSM data
│   ├── build_graph.py           # Build NetworkX graph
│   ├── compute_scores.py        # Pre-compute safety scores
│   ├── query_pois.py            # Query Overpass API for POIs
│   └── validate_data.py         # Data quality checks
├── docs/
│   ├── API.md                   # API documentation
│   ├── ALGORITHM.md             # Safety scoring algorithm docs
│   └── DEMO_SCRIPT.md           # 5-minute demo script
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
├── .env.example
└── README.md
```

---

## PHASE 1: E2E TESTING (Write Tests First)

### 1.1 Feature Specifications (What We Test Against)

#### FEATURE 1: Route Planning
```
GIVEN: User opens the app
WHEN:  User enters start point (MUJ) and end point (Jaipur Railway Station)
THEN:  Map shows 3 routes:
       - Red route (fastest, lower safety)
       - Green route (safest, longer)
       - Blue route (recommended, balanced)
AND:   Sidebar shows safety score breakdown
AND:   Sidebar shows AI-generated explanation
AND:   Each route shows estimated time and distance
```

#### FEATURE 2: Night Mode
```
GIVEN: Routes are displayed on map
WHEN:  User toggles "Night Mode" switch
THEN:  Safety scores recalculate with nighttime factors
AND:   Routes potentially change (safer alternatives)
AND:   Heatmap shifts (isolated areas become more red)
AND:   Sidebar updates: "Route now avoids Industrial Area Road"
AND:   Animation shows the transition
```

#### FEATURE 3: Safety Heatmap
```
GIVEN: User navigates to heatmap page
WHEN:  Map loads
THEN:  Entire city shows color-coded safety overlay
AND:   Time slider is visible (6 AM to midnight)
AND:   Dragging slider changes heatmap colors in real-time
AND:   Clicking a road segment shows its safety breakdown
```

#### FEATURE 4: Emergency Mode
```
GIVEN: User is on any page
WHEN:  User clicks "Emergency" button
THEN:  Panel shows:
       - Nearest police station (name + distance + ETA)
       - Nearest hospital (name + distance + ETA)
       - Nearest safe public space
       - Emergency numbers (100, 108, 112, 1091)
       - "Share Location" button
```

#### FEATURE 5: Community Reporting
```
GIVEN: User sees a safety issue
WHEN:  User clicks "Report Issue" and selects type + location
THEN:  Report is saved with timestamp
AND:   Report appears as warning marker on map
AND:   Reports older than 6 hours fade out
AND:   Multiple reports at same location increase weight
```

#### FEATURE 6: School Route Mode
```
GIVEN: User navigates to school route page
WHEN:  User enters home + school location
THEN:  System finds safest walking route for children
AND:   Route prioritizes: main roads, school zones, police proximity
AND:   Route avoids: isolated areas, liquor establishments
AND:   Shows "Child Safety Score" (different weighting than adult)
```

#### FEATURE 7: City Admin Dashboard
```
GIVEN: User navigates to admin page
WHEN:  Dashboard loads
THEN:  Shows:
       - Top 10 most dangerous zones
       - Safety improvement recommendations
       - Heatmap with infrastructure overlay
       - Before/after simulation ("if we add lights here...")
```

### 1.2 E2E Test Cases (Playwright/Selenium)

```python
# tests/test_e2e.py

class TestRoutePlanning:
    def test_route_planner_loads(self):
        """Page loads with map, search bar, and empty state"""

    def test_search_returns_three_routes(self):
        """Searching A->B returns 3 colored routes on map"""

    def test_routes_have_safety_scores(self):
        """Each route displays safety score and breakdown"""

    def test_routes_have_ai_explanation(self):
        """Each route has Groq-generated explanation text"""

    def test_fastest_route_is_red(self):
        """Fastest route polyline is red on map"""

    def test_safest_route_is_green(self):
        """Safest route polyline is green on map"""

    def test_recommended_route_is_blue(self):
        """Recommended route polyline is blue on map"""

    def test_clicking_route_shows_details(self):
        """Clicking a route highlights it and shows full breakdown"""

    def test_search_with_invalid_coordinates(self):
        """Invalid input shows error, not crash"""

    def test_search_with_same_start_end(self):
        """Same start+end shows message, not empty map"""

class TestNightMode:
    def test_night_mode_toggle_exists(self):
        """Toggle switch is visible on route planner"""

    def test_night_mode_changes_routes(self):
        """Toggling night mode recalculates and redraws routes"""

    def test_night_mode_changes_heatmap(self):
        """Heatmap colors shift when night mode toggled"""

    def test_night_mode_shows_changes_sidebar(self):
        """Sidebar shows what changed: 'Route now avoids X'"""

    def test_night_mode_animation(self):
        """Transition between day/night is animated, not instant"""

class TestSafetyHeatmap:
    def test_heatmap_page_loads(self):
        """Heatmap page shows map with color overlay"""

    def test_time_slider_exists(self):
        """Time slider (6AM-midnight) is visible"""

    def test_slider_changes_heatmap(self):
        """Dragging slider updates heatmap colors"""

    def test_clicking_segment_shows_breakdown(self):
        """Clicking a road shows its 7-factor safety breakdown"""

    def test_heatmap_legend_visible(self):
        """Color legend (red=danger, green=safe) is shown"""

class TestEmergencyMode:
    def test_emergency_button_always_visible(self):
        """Emergency button visible on every page"""

    def test_emergency_shows_nearest_police(self):
        """Shows nearest police station with distance"""

    def test_emergency_shows_nearest_hospital(self):
        """Shows nearest hospital with distance"""

    def test_emergency_shows_numbers(self):
        """Shows 100, 108, 112, 1091"""

    def test_share_location_button_works(self):
        """Share location generates a copyable link"""

class TestCommunityReporting:
    def test_report_button_visible(self):
        """Report issue button is accessible"""

    def test_submit_report_saves(self):
        """Submitting a report stores it in database"""

    def test_report_appears_on_map(self):
        """Submitted report shows as marker on map"""

    def test_old_reports_fade(self):
        """Reports older than 6 hours are visually faded"""

class TestSchoolRoutes:
    def test_school_page_loads(self):
        """School route page has home + school inputs"""

    def test_school_route_prioritizes_safety(self):
        """School route scores higher safety than fastest route"""

    def test_school_route_avoids_liquor(self):
        """School route doesn't pass through liquor establishments"""

class TestAdminDashboard:
    def test_admin_page_loads(self):
        """Admin dashboard shows analytics"""

    def test_shows_dangerous_zones(self):
        """Top 10 dangerous zones are listed"""

    def test_shows_recommendations(self):
        """AI recommendations for safety improvements shown"""

class TestUIResponsiveness:
    def test_mobile_layout(self):
        """App is usable on mobile viewport (375px)"""

    def test_tablet_layout(self):
        """App is usable on tablet viewport (768px)"""

    def test_desktop_layout(self):
        """App is usable on desktop viewport (1920px)"""

    def test_map_takes_majority_of_screen(self):
        """Map occupies at least 60% of viewport"""

    def test_sidebar_collapses_on_mobile(self):
        """Sidebar collapses to bottom sheet on mobile"""

    def test_loading_states(self):
        """Loading spinner shows while routes are being calculated"""

    def test_error_states(self):
        """Network errors show user-friendly message, not stack trace"""

class TestAccessibility:
    def test_keyboard_navigation(self):
        """All interactive elements reachable via Tab"""

    def test_color_contrast(self):
        """Text passes WCAG AA contrast ratio"""

    def test_screen_reader_labels(self):
        """All buttons/inputs have aria-labels"""

    def test_focus_indicators(self):
        """Focused elements have visible outline"""
```

### 1.3 API Integration Tests

```python
# tests/test_api.py

class TestRouteAPI:
    def test_post_route_valid_coordinates(self):
        """POST /api/route with valid lat/lng returns 3 routes"""

    def test_post_route_missing_coordinates(self):
        """POST /api/route without coordinates returns 400"""

    def test_post_route_outside_jaipur(self):
        """POST /api/route with coords outside Jaipur returns 404"""

    def test_route_response_structure(self):
        """Response contains: routes[], safety_scores, explanation"""

    def test_route_night_mode_parameter(self):
        """POST /api/route?night=true returns night-adjusted scores"""

class TestHeatmapAPI:
    def test_heatmap_data_returns_geojson(self):
        """GET /api/heatmap returns valid GeoJSON"""

    def test_heatmap_respects_time_parameter(self):
        """GET /api/heatmap?hour=22 returns night data"""

class TestEmergencyAPI:
    def test_emergency_finds_nearest_police(self):
        """GET /api/emergency?lat=X&lng=Y returns nearest police"""

    def test_emergency_finds_nearest_hospital(self):
        """GET /api/emergency?lat=X&lng=Y returns nearest hospital"""

class TestCommunityAPI:
    def test_submit_report(self):
        """POST /api/report creates new report"""

    def test_get_reports(self):
        """GET /api/reports returns all active reports"""

    def test_expired_reports_not_returned(self):
        """Reports older than 24h excluded from GET"""
```

### 1.4 Unit Tests

```python
# tests/test_safety_engine.py

class TestSafetyScoring:
    def test_well_lit_road_scores_high(self):
        """Road with shops + lighting scores > 70"""

    def test_isolated_road_scores_low(self):
        """Industrial road with no POIs scores < 30"""

    def test_night_reduces_score(self):
        """Same road scores lower at 2AM than 2PM"""

    def test_police_proximity_boosts_score(self):
        """Road near police station gets proximity bonus"""

    def test_score_bounds_0_to_100(self):
        """All scores clamped between 0 and 100"""

    def test_score_components_sum_correctly(self):
        """7 weighted components sum to final score"""

# tests/test_route_optimizer.py

class TestRouteOptimization:
    def test_shortest_path_found(self):
        """Fastest route is actually shortest time"""

    def test_safest_path_found(self):
        """Safest route has highest average safety score"""

    def test_balanced_route_is_pareto_optimal(self):
        """Recommended route is on Pareto frontier"""

    def test_three_routes_are_distinct(self):
        """Fastest, safest, recommended are different routes"""

    def test_no_route_found_returns_empty(self):
        """Disconnected graph returns empty, not crash"""
```

---

## PHASE 2: VALIDATION & IMPROVEMENT

### 2.1 After E2E Tests Are Written — Validate Before Building

| Check Item | What We Validate | How |
|---|---|---|
| Data availability | Can we actually get Jaipur OSM data? | Run download_osm.py |
| Graph buildability | Can we build a road network graph? | Run build_graph.py on sample |
| POI coverage | Are police stations/hospitals mapped in OSM? | Run query_pois.py, count results |
| Safety score sanity | Do scores make intuitive sense? | Compare known safe vs unsafe areas |
| Route quality | Do routes avoid obviously bad areas? | Manual check on 5 test cases |
| Groq latency | Can Groq generate explanation in < 3 sec? | Time 10 API calls |
| Map performance | Can Leaflet handle 50K+ road segments? | Load test with full Jaipur data |
| Night mode delta | Do scores actually change enough at night? | Compare day vs night for 100 segments |

### 2.2 Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| OSM data incomplete for Jaipur | Medium | High | Supplement with manual data + simulated POIs |
| Safety scores feel arbitrary | Medium | High | Validate against known safe/unsafe areas, tune weights |
| Groq API rate limits | Low | Medium | Cache explanations, fallback to templates |
| Map performance with full data | Medium | High | Pre-cluster data, use vector tiles, lazy load |
| Night mode doesn't change enough | Low | Medium | Increase night penalty weights |
| No real crime data at street level | High | Medium | Use proxy factors (lighting, isolation, POI density) |
| Demo internet failure | Low | Critical | Pre-cache EVERYTHING, offline fallback |
| Judges ask "how accurate is safety score?" | High | Medium | Prepare answer: "7-factor model validated against..." |

---

## PHASE 3: FUTURE CHALLENGES (Post-Hackathon)

### Challenge 1: Real Crime Data Integration
- **Problem:** NCRB data is district-level, not street-level
- **Solution:** Partner with state police for FIR data access, or use RTI to get ward-level data
- **Timeline:** 2-3 months post-hackathon

### Challenge 2: Real-Time Crowd Density
- **Problem:** We simulate crowd density from time models
- **Solution:** Integrate Google Popular Times API, or cellular density data from telecom providers
- **Timeline:** 3-6 months

### Challenge 3: Multi-City Expansion
- **Problem:** Currently hardcoded for Jaipur
- **Solution:** Abstract data layer — same code works for any city with OSM data
- **Timeline:** 1 month (architecture refactor)

### Challenge 4: Mobile App
- **Problem:** Web app doesn't work well for walking navigation
- **Solution:** React Native or Flutter app with GPS tracking + turn-by-turn
- **Timeline:** 3-4 months

### Challenge 5: Offline Mode
- **Problem:** Requires internet for map tiles + API calls
- **Solution:** Pre-download map tiles for city, cache routes locally
- **Timeline:** 1-2 months

### Challenge 6: Government Partnership
- **Problem:** Real impact needs government adoption
- **Solution:** Pitch to Smart Cities Mission, Jaipur Municipal Corporation
- **Timeline:** Ongoing

### Challenge 7: User Privacy & Data Protection
- **Problem:** Location data is sensitive
- **Solution:** No user accounts, no location storage, client-side routing, DPDP Act compliance
- **Timeline:** Design-time (built into architecture)

### Challenge 8: Safety Score Accuracy Validation
- **Problem:** How do we KNOW our scores are accurate?
- **Solution:** Validate against: (a) police crime maps, (b) user feedback surveys, (c) expert review from women's safety organizations
- **Timeline:** 2-3 months

### Challenge 9: Handling Adversarial Reports
- **Problem:** Users could file false safety reports (prank, revenge)
- **Solution:** Report verification system — multiple independent reports needed to affect score, rate limiting, anomaly detection
- **Timeline:** 1 month

### Challenge 10: Integration with Existing Apps
- **Problem:** Users won't switch from Google Maps
- **Solution:** Build as an API/layer that Google Maps, Ola, Uber can integrate
- **Timeline:** 6+ months (needs partnerships)

---

## PHASE 4: UI/UX LAYOUT SPECIFICATION

### Page 1: Route Planner (Main Page)

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER                                                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 🛡️ SafeRoute    [Heatmap] [School] [Admin]    [🌙Night] │ │
│ └─────────────────────────────────────────────────────────┘ │
├────────────────────────────┬────────────────────────────────┤
│ SIDEBAR (30%)              │ MAP (70%)                      │
│                            │                                │
│ ┌──────────────────────┐   │  ┌──────────────────────────┐ │
│ │ 📍 From: [MUJ      ] │   │  │                          │ │
│ │ 📍 To:   [Station  ] │   │  │     LEAFLET MAP          │ │
│ │ [🔍 Find Safe Routes]│   │  │     with OSM tiles       │ │
│ └──────────────────────┘   │  │                          │ │
│                            │  │  Red polyline (fastest)  │ │
│ ┌──────────────────────┐   │  │  Green polyline (safest) │ │
│ │ ROUTES               │   │  │  Blue polyline (best)    │ │
│ │                      │   │  │                          │ │
│ │ 🔴 Fastest  20min    │   │  │  [Police markers]        │ │
│ │    Safety: 3/10 ⚠️   │   │  │  [Hospital markers]      │ │
│ │                      │   │  │  [Report markers]        │ │
│ │ 🟢 Safest   35min    │   │  │                          │ │
│ │    Safety: 9/10 ✅   │   │  │                          │ │
│ │                      │   │  │                          │ │
│ │ 🔵 Best     25min    │   │  │                          │ │
│ │    Safety: 8/10 ✅   │   │  │                          │ │
│ └──────────────────────┘   │  └──────────────────────────┘ │
│                            │                                │
│ ┌──────────────────────┐   │  ┌──────────────────────────┐ │
│ │ SAFETY BREAKDOWN     │   │  │ [Emergency 🚨] [Report ⚠️]│ │
│ │ 🏮 Lighting:    8/10 │   │  └──────────────────────────┘ │
│ │ 🚔 Police:      9/10 │   │                                │
│ │ 👥 Crowd:       7/10 │   │                                │
│ │ 🛣️ Road Type:   8/10 │   │                                │
│ │ 📊 Crime Data:  6/10 │   │                                │
│ │ ♿ Accessible:   5/10 │   │                                │
│ │ 📢 Reports:     9/10 │   │                                │
│ └──────────────────────┘   │                                │
│                            │                                │
│ ┌──────────────────────┐   │                                │
│ │ 🤖 AI EXPLANATION    │   │                                │
│ │ "Route C is recom-   │   │                                │
│ │ mended because it    │   │                                │
│ │ passes through 3     │   │                                │
│ │ well-lit commercial  │   │                                │
│ │ areas, is 200m from  │   │                                │
│ │ Sindhi Camp police   │   │                                │
│ │ station, and avoids  │   │                                │
│ │ the isolated stretch │   │                                │
│ │ near Industrial Area │   │                                │
│ │ Railway Crossing."   │   │                                │
│ └──────────────────────┘   │                                │
├────────────────────────────┴────────────────────────────────┤
│ FOOTER: Built for IIC 3.0 | Women & Child Safety            │
└─────────────────────────────────────────────────────────────┘
```

### Page 2: Safety Heatmap

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER                                                       │
├────────────────────────────┬────────────────────────────────┤
│ CONTROLS (30%)             │ MAP (70%)                      │
│                            │                                │
│ ┌──────────────────────┐   │  ┌──────────────────────────┐ │
│ │ TIME OF DAY          │   │  │                          │ │
│ │ [6AM ●──────── 12AM] │   │  │  FULL CITY HEATMAP       │ │
│ │ Current: 9:47 PM     │   │  │  Red = dangerous         │ │
│ └──────────────────────┘   │  │  Yellow = moderate       │ │
│                            │  │  Green = safe             │ │
│ ┌──────────────────────┐   │  │                          │ │
│ │ LEGEND               │   │  │  [Click segment for      │ │
│ │ 🔴 0-30  Dangerous   │   │  │   breakdown]             │ │
│ │ 🟡 31-60 Moderate    │   │  │                          │ │
│ │ 🟢 61-100 Safe       │   │  │                          │ │
│ └──────────────────────┘   │  └──────────────────────────┘ │
│                            │                                │
│ ┌──────────────────────┐   │                                │
│ │ TOP DANGEROUS ZONES  │   │                                │
│ │ 1. Industrial Area   │   │                                │
│ │    Score: 12/100     │   │                                │
│ │ 2. Sitapura SEZ Rd   │   │                                │
│ │    Score: 18/100     │   │                                │
│ │ 3. Mansarovar Back Rd│   │                                │
│ │    Score: 24/100     │   │                                │
│ └──────────────────────┘   │                                │
├────────────────────────────┴────────────────────────────────┤
│ FOOTER                                                       │
└─────────────────────────────────────────────────────────────┘
```

### Page 3: Emergency Mode (Overlay)

```
┌─────────────────────────────────────────────────────────────┐
│ (Background: current page dimmed)                            │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │                    🚨 EMERGENCY                          │ │
│ │                                                          │ │
│ │  NEAREST POLICE STATION                                  │ │
│ │  Ashok Nagar PS     800m    ~3 min walk                  │ │
│ │  [📍 Navigate] [📞 Call 100]                             │ │
│ │                                                          │ │
│ │  NEAREST HOSPITAL                                        │ │
│ │  SMS Hospital       1.2km   ~5 min walk                  │ │
│ │  [📍 Navigate] [📞 Call 108]                             │ │
│ │                                                          │ │
│ │  NEAREST SAFE SPACE                                      │ │
│ │  HP Petrol Pump     200m    ~2 min walk                  │ │
│ │  [📍 Navigate]                                           │ │
│ │                                                          │ │
│ │  ────────────────────────────────────                    │ │
│ │  EMERGENCY NUMBERS                                       │ │
│ │  📞 100 — Police                                         │ │
│ │  📞 108 — Ambulance                                      │ │
│ │  📞 112 — Emergency                                      │ │
│ │  📞 1091 — Women Helpline                                │ │
│ │                                                          │ │
│ │  [📤 Share My Location]  [✕ Close]                       │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Page 4: School Route Mode

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER                                                       │
├────────────────────────────┬────────────────────────────────┤
│ CONTROLS (30%)             │ MAP (70%)                      │
│                            │                                │
│ ┌──────────────────────┐   │  ┌──────────────────────────┐ │
│ │ 🏠 Home:  [________] │   │  │                          │ │
│ │ 🏫 School: [________]│   │  │  SCHOOL ROUTE MAP        │ │
│ │ ⏰ Depart: [8:00 AM] │   │  │                          │ │
│ │ [Find Safe Route]    │   │  │  Blue route (safest      │ │
│ └──────────────────────┘   │  │  for children)           │ │
│                            │  │                          │ │
│ ┌──────────────────────┐   │  │  [School markers]        │ │
│ │ CHILD SAFETY SCORE   │   │  │  [Crossing guards]       │ │
│ │ Overall: 9/10 ✅     │   │  │  [Police proximity]      │ │
│ │                      │   │  │                          │ │
│ │ ✅ Main roads only    │   │  │                          │ │
│ │ ✅ Near school zones  │   │  │                          │ │
│ │ ✅ Well-lit path      │   │  │                          │ │
│ │ ❌ No liquor shops    │   │  │                          │ │
│ │ ❌ No isolated areas  │   │  │                          │ │
│ └──────────────────────┘   │  └──────────────────────────┘ │
├────────────────────────────┴────────────────────────────────┤
│ FOOTER                                                       │
└─────────────────────────────────────────────────────────────┘
```

### Page 5: City Admin Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│ HEADER                                                       │
├──────────────────────────────────────────────────────────────┤
│ STATS BAR                                                     │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│ │ Avg Score │ │ Danger   │ │ Reports  │ │ Coverage │        │
│ │   62/100  │ │ 12 zones │ │   847    │ │   94%    │        │
│ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │
├────────────────────────────┬────────────────────────────────┤
│ ANALYTICS (50%)            │ MAP (50%)                      │
│                            │                                │
│ ┌──────────────────────┐   │  ┌──────────────────────────┐ │
│ │ TOP 10 DANGER ZONES  │   │  │                          │ │
│ │ 1. Industrial Area   │   │  │  HEATMAP WITH            │ │
│ │ 2. Sitapura SEZ      │   │  │  INFRASTRUCTURE          │ │
│ │ 3. Mansarovar Back   │   │  │  OVERLAY                 │ │
│ │ ...                  │   │  │                          │ │
│ └──────────────────────┘   │  │  [Police station icons]  │ │
│                            │  │  [Street light coverage]  │ │
│ ┌──────────────────────┐   │  │  [CCTV locations]        │ │
│ │ AI RECOMMENDATIONS   │   │  │                          │ │
│ │ "Add 15 street lights│   │  │                          │ │
│ │  on Industrial Area  │   │  │                          │ │
│ │  Road to increase    │   │  │                          │ │
│ │  safety score from   │   │  │                          │ │
│ │  12 to 67 (+458%)"  │   │  │                          │ │
│ │                      │   │  │                          │ │
│ │ "Install CCTV at     │   │  │                          │ │
│ │  Sitapura Junction"  │   │  │                          │ │
│ └──────────────────────┘   │  └──────────────────────────┘ │
├────────────────────────────┴────────────────────────────────┤
│ FOOTER                                                       │
└──────────────────────────────────────────────────────────────┘
```

---

## PHASE 5: COLOR SCHEME & DESIGN SYSTEM

```
PRIMARY:     #6C4CE0 (Purple — user's preference)
SECONDARY:   #1A1A2E (Dark navy — for dark elements)
ACCENT:      #00D4AA (Teal — for safe/positive indicators)
DANGER:      #FF4757 (Red — for danger/warnings)
WARNING:     #FFA502 (Orange — for caution)
SAFE:        #2ED573 (Green — for safe indicators)
BACKGROUND:  #F8F9FA (Light gray)
TEXT:        #2D3436 (Near black)
SURFACE:     #FFFFFF (White cards/panels)

ROUTE COLORS:
  Fastest:    #FF4757 (Red)
  Safest:     #2ED573 (Green)
  Recommended: #6C4CE0 (Purple — matches brand)

HEATMAP SCALE:
  0-30:   #FF4757 (Red — dangerous)
  31-60:  #FFA502 (Orange — moderate)
  61-100: #2ED573 (Green — safe)
```

---

## PHASE 6: API SPECIFICATION

### Endpoints

```
POST /api/route
  Body: { "start": [lat, lng], "end": [lat, lng], "night": false, "mode": "normal|school" }
  Response: {
    "routes": [
      { "type": "fastest", "coordinates": [...], "time": 20, "distance": 5.2, "safety_score": 32 },
      { "type": "safest", "coordinates": [...], "time": 35, "distance": 8.1, "safety_score": 91 },
      { "type": "recommended", "coordinates": [...], "time": 25, "distance": 6.3, "safety_score": 78 }
    ],
    "safety_breakdown": {
      "lighting": 8, "police": 9, "crowd": 7, "road_type": 8,
      "crime": 6, "accessibility": 5, "reports": 9
    },
    "explanation": "Route C is recommended because..."
  }

GET /api/heatmap?hour=22
  Response: {
    "type": "FeatureCollection",
    "features": [
      { "type": "Feature", "geometry": {...}, "properties": { "safety_score": 45, "segment_id": "..." } }
    ]
  }

GET /api/emergency?lat=26.9124&lng=75.7873
  Response: {
    "police": { "name": "Ashok Nagar PS", "lat": ..., "lng": ..., "distance": 800, "eta_minutes": 3 },
    "hospital": { "name": "SMS Hospital", "lat": ..., "lng": ..., "distance": 1200, "eta_minutes": 5 },
    "safe_space": { "name": "HP Petrol Pump", "lat": ..., "lng": ..., "distance": 200, "eta_minutes": 2 }
  }

POST /api/report
  Body: { "lat": ..., "lng": ..., "type": "broken_light|suspicious|no_cctv|stray_dogs|other", "description": "..." }
  Response: { "id": "...", "status": "recorded" }

GET /api/reports
  Response: { "reports": [{ "id": "...", "lat": ..., "lng": ..., "type": "...", "timestamp": "...", "weight": 0.8 }] }

GET /api/admin/stats
  Response: { "avg_score": 62, "danger_zones": [...], "total_reports": 847, "recommendations": [...] }
```

---

## PHASE 7: BUILD ORDER (TDD)

```
Step 1: Write test_safety_engine.py (unit tests)
Step 2: Implement safety_engine.py to pass tests
Step 3: Write test_route_optimizer.py (unit tests)
Step 4: Implement route_optimizer.py to pass tests
Step 5: Write test_api.py (integration tests)
Step 6: Implement Flask API to pass tests
Step 7: Write test_e2e.py (browser tests)
Step 8: Implement frontend to pass e2e tests
Step 9: Validate all tests pass
Step 10: Polish, demo prep, deploy
```

---

## ACCEPTANCE CRITERIA (DONE = )

- [ ] All unit tests pass (safety engine, route optimizer)
- [ ] All API tests pass (route, heatmap, emergency, reports)
- [ ] All E2E tests pass (7 features × multiple scenarios)
- [ ] Night mode recalculates routes with visible change
- [ ] Heatmap loads in < 3 seconds for full Jaipur
- [ ] Emergency mode finds nearest points in < 1 second
- [ ] Groq explanation generates in < 3 seconds
- [ ] Mobile responsive (sidebar collapses on small screens)
- [ ] Works offline (pre-cached data) for demo
- [ ] 5-minute demo script practiced 3 times
