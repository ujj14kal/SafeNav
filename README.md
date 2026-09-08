# 🛡️ SafeNav — Women & Child Safety Navigation Platform

> **IIC 3.0 Hackathon | PS 22 — Safe Route for Women Safety**

SafeNav is an AI-powered safety navigation platform that recommends the safest routes between locations by analyzing real-time data including road lighting, police proximity, crowd density, road type, and community feedback.

---

## 🌐 Live Demo

**Access the app on your browser or phone:**

```
http://localhost:5000
```

**On the same WiFi network (phone/laptop):**
```
http://10.58.193.231:5000
```

**GitHub Repository:**
```
https://github.com/ujj14kal/safestroute
```

---

## 📱 Pages

| Page | URL | Description |
|------|-----|-------------|
| 🗺️ Route Planner | `/` | Find safest routes between two locations |
| 🔥 Heatmap | `/heatmap` | City-wide safety visualization with colored road lines |
| 🏫 School Safety | `/school` | Safe routes for children with geofencing & live tracking |
| 📊 Admin Dashboard | `/admin` | Safety intelligence for city officials (login: admin / admin123) |

---

## ✨ Key Features

### Route Planning
- **3 route options**: Fastest, Safest, Recommended
- Real road paths via Google Directions API
- Safety scoring based on 7 factors (lighting, police, crowd, road type, crime, accessibility, reports)
- Time-of-day safety analysis (routes are safer during daytime)
- AI safety briefing with contextual tips

### Safety Heatmap
- Color-coded road lines on real Google Maps
- Red = Dangerous | Orange = Moderate | Green = Safe
- Time slider to see safety changes throughout the day
- Click any road segment for detailed safety info

### School Safety Mode
- Safe route planning for children
- Geofencing with Home (200m) and School (300m) zones
- Live location tracking simulation
- SOS emergency alerts
- Emergency contacts (Mom, Dad, School Admin, Police)

### Feedback System
- 👍 Safe / 👎 Unsafe feedback tied to exact locations
- Feedback dynamically updates safety scores
- Real location names (reverse geocoded)

### SOS & Emergency
- One-tap SOS button with pulsing alert
- Nearest police station and hospital detection
- Emergency numbers: 100 (Police), 108 (Ambulance), 112 (Emergency), 1091 (Women Helpline)
- Guardian network with SMS alerts

### User System
- User registration with full name, email, phone
- Login with username/password
- Profile stored in database
- Admin dashboard with police evidence database

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask, SQLAlchemy |
| Database | SQLite |
| Algorithms | NetworkX (graph routing), cuOpt-inspired safety-cost optimization |
| Data Sources | OpenStreetMap (roads), Google Places API (POIs) |
| Maps | Google Maps JavaScript API, Directions API, Places API |
| AI | Groq AI for safety explanations |
| Frontend | HTML, CSS, JavaScript, Tailwind CSS |

---

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/ujj14kal/safestroute.git
cd safestroute

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your Google Maps API key

# Run
python run.py
```

Open http://localhost:5000 in your browser.

---

## 📊 Database Schema

- **SafetyFeedback** — User safe/unsafe feedback with location
- **Incident** — Reported safety incidents
- **LocationZone** — Pre-defined safety zones with base scores
- **Recording** — Audio recordings from SOS events
- **Journey** — Her Way Home journey monitoring
- **User** — User accounts with profile info
- **Guardian** — Emergency guardian contacts
- **SOSHistory** — SOS event log

---

## 🧪 Testing

```bash
pytest tests/ -q --ignore=tests/test_e2e.py
# 53 tests passing
```

---

## 📄 License

Built for IIC 3.0 Hackathon — Manipal University Jaipur

---

**SafeNav** — Because every route should be a safe route. 🛡️
