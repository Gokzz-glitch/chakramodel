import { useEffect, useMemo, useState } from 'react'
import './index.css'

const observed = [82, 88, 75, 96, 101, 91, 110, 124, 118, 96, 89, 94, 105, 99, 112, 108, 97, 103, 116, 109, 121, 134, 128, 119, 113, 125, 130, 144]
const forecast = [132, 139, 151, 146, 158, 172, 166]
const forecastDays = ['Mon 14', 'Tue 15', 'Wed 16', 'Thu 17', 'Fri 18', 'Sat 19', 'Sun 20']
const observations = [
  ['Sep 13, 2026', 124, 'Unhealthy for sensitive groups', 'PM2.5'],
  ['Sep 12, 2026', 118, 'Unhealthy for sensitive groups', 'PM2.5'],
  ['Sep 11, 2026', 96, 'Moderate', 'PM10'],
  ['Sep 10, 2026', 89, 'Moderate', 'PM2.5'],
]
const locations = {
  'Chennai, IN': { latitude: 13.0827, longitude: 80.2707 },
  'Krishnagiri, IN': { latitude: 12.5186, longitude: 78.2137 },
  'Salem, IN': { latitude: 11.6643, longitude: 78.1460 },
  'Washington, US': { latitude: 38.9072, longitude: -77.0369 },
  'Moscow, RU': { latitude: 55.7558, longitude: 37.6173 },
  'Russia (national view)': { latitude: 55.7558, longitude: 37.6173 },
}

function Icon({ name, size = 18 }) {
  const shapes = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    chart: <><path d="M4 19V5M4 19h17M7 15l4-5 3 2 5-7" /></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" /></>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v7c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12v7c0 1.7 3.6 3 8 3s8-1.3 8-3v-7" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a2 2 0 1 0 0 2.8 2 2 0 0 0 2.8-2.8 2 2 0 0 0 0-6 2 2 0 1 0-2.8-2.8 2 2 0 0 0-2.8 0 2 2 0 1 0-2.8 2.8 2 2 0 0 0-6 0 2 2 0 1 0 2.8 2.8 2 2 0 1 0 0 2.8 2 2 0 1 0 0 6 2 2 0 1 0 2.8 2.8 2 2 0 1 0 2.8 0Z" /></>,
    upload: <><path d="M12 16V4m-5 5 5-5 5 5M5 20h14" /></>,
    arrow: <><path d="M5 12h14m-6-6 6 6-6 6" /></>,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{shapes[name]}</svg>
}

function ForecastChart() {
  const point = (value, index) => `${index * 3.1 + 3},${106 - value * 0.55}`
  const observedPoints = observed.map(point).join(' ')
  const forecastPoints = forecast.map((value, index) => `${90 + index * 3.1},${106 - value * 0.55}`).join(' ')
  return <div className="chart-wrap">
    <svg viewBox="0 0 112 115" preserveAspectRatio="none" className="aqi-chart">
      <defs><linearGradient id="chart-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#ed795d" stopOpacity=".28" /><stop offset="100%" stopColor="#ed795d" stopOpacity="0" /></linearGradient></defs>
      {[25, 50, 75, 100].map((y) => <line key={y} x1="3" x2="109" y1={y} y2={y} className="chart-grid" />)}
      <path d={`M 3,106 L ${observedPoints} L 90,106 Z`} fill="url(#chart-fill)" />
      <polyline points={observedPoints} className="history-line" />
      <line x1="90" x2="90" y1="10" y2="106" className="today-line" />
      <polyline points={forecastPoints} className="forecast-line" />
      {forecast.map((value, index) => <circle key={value} cx={90 + index * 3.1} cy={106 - value * 0.55} r="1.5" className="forecast-dot" />)}
    </svg>
    <div className="chart-labels"><span>Sep 01</span><span>Today</span><span>Sep 20</span></div>
  </div>
}

function App() {
  const [active, setActive] = useState('Overview')
  const [range, setRange] = useState('7 days')
  const [location, setLocation] = useState('Chennai, IN')
  const [notifications, setNotifications] = useState(true)
  const [showAll, setShowAll] = useState(false)
  const [toast, setToast] = useState('')
  const [liveAqi, setLiveAqi] = useState(null)
  const [liveStatus, setLiveStatus] = useState('Connecting to live air quality…')
  const maxForecast = useMemo(() => Math.max(...forecast), [])
  useEffect(() => {
    const coordinates = locations[location]
    const controller = new AbortController()
    fetch(`https://air-quality-api.open-meteo.com/v1/air-quality?latitude=${coordinates.latitude}&longitude=${coordinates.longitude}&current=us_aqi,pm2_5,pm10&timezone=auto`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Live air-quality request failed')
        return response.json()
      })
      .then((data) => {
        setLiveAqi({ value: Math.round(data.current.us_aqi), pm25: data.current.pm2_5, pm10: data.current.pm10 })
        setLiveStatus(`Live · ${new Date(data.current.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`)
      })
      .catch((error) => {
        if (error.name !== 'AbortError') setLiveStatus('Live service unavailable · showing dataset')
      })
    return () => controller.abort()
  }, [location])
  const notify = (message) => {
    setToast(message)
    window.setTimeout(() => setToast(''), 2600)
  }

  const navItems = [['Overview', 'grid'], ['Forecasts', 'chart'], ['Alerts', 'bell'], ['Data sources', 'database'], ['Open-source toolkit', 'settings']]
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><span /></div><div><strong>AAAM</strong><small>Air intelligence</small></div></div>
      <div className="workspace"><span className="workspace-dot" /> AAAM AQI Dataset <span className="chevron">⌄</span></div>
      <p className="nav-label">Workspace</p>
      <nav>{navItems.map(([label, icon]) => <button key={label} className={`nav-item ${active === label ? 'selected' : ''}`} onClick={() => setActive(label)}><Icon name={icon} /> {label}{label === 'Alerts' && <span className="nav-badge">3</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="model-status"><span className="status-dot" /><div><b>Model online</b><small>Updated 8 min ago</small></div></div><button className="user-card" onClick={() => notify('Profile settings are coming soon.')}><span className="avatar">AK</span><span><b>Arjun Kumar</b><small>Administrator</small></span><span className="more">•••</span></button></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><div className="eyebrow">AAAM / AIR QUALITY / LIVE MONITORING</div><h1>{active === 'Overview' ? 'Good morning, Arjun' : active}</h1><div className="live-status"><span className={`status-dot ${liveAqi ? '' : 'pulse'}`} /> {liveStatus}</div></div><div className="header-actions"><label className="location"><span>⌖</span><select value={location} onChange={(event) => { setLocation(event.target.value); setLiveStatus('Updating live reading…'); setLiveAqi(null) }}>{Object.keys(locations).map((name) => <option key={name}>{name}</option>)}</select></label><button className={`icon-button ${notifications ? 'has-alert' : ''}`} onClick={() => setNotifications(!notifications)} aria-label="Toggle notifications"><Icon name="bell" /></button><button className="primary-button" onClick={() => notify('Forecast refreshed using the latest uploaded data.')}><Icon name="upload" size={16} /> Update data</button></div></header>
      {active !== 'Overview' ? <Module active={active} onBack={() => setActive('Overview')} notify={notify} /> : <><section className="alert-banner"><div className="alert-icon"><Icon name="bell" /></div><div><b>Elevated AQI expected this weekend</b><p>AAAM's baseline projection detects a <strong>72% probability</strong> of a spike above 150 between Sat 19 – Sun 20 Sep.</p></div><button onClick={() => setActive('Alerts')}>View alert <Icon name="arrow" size={15} /></button><span className="dismiss" onClick={(event) => event.currentTarget.parentElement.remove()}>×</span></section>
        <section className="stat-grid"><div className="stat-card"><div className="stat-top"><span>Current AQI</span><span className="status-pill moderate">Live</span></div><div className="stat-value">{liveAqi?.value ?? 124} <small>US AQI</small></div><div className="stat-delta down">PM2.5 {liveAqi?.pm25 ?? '—'} µg/m³ <em>real-time</em></div><div className="mini-bars">{[40, 55, 44, 71, 58, 64, 49, 68, 62, 55, 48, 53].map((height, i) => <i key={i} style={{ height: `${height}%` }} />)}</div></div><div className="stat-card"><div className="stat-top"><span>Next 7-day avg.</span><span className="trend-up">↗</span></div><div className="stat-value">153 <small>US AQI</small></div><div className="stat-delta up">↑ 23.4% <em>vs this week</em></div><div className="sparkline"><svg viewBox="0 0 150 35" preserveAspectRatio="none"><polyline points="0,28 16,25 30,27 45,20 59,22 72,14 88,18 103,9 116,13 132,5 150,8" /></svg></div></div><div className="stat-card"><div className="stat-top"><span>Spike likelihood</span><span className="status-pill high">High risk</span></div><div className="stat-value">72 <small>%</small></div><div className="stat-delta up">↑ 16.1% <em>in last 24h</em></div><div className="risk-meter"><span style={{ width: `${maxForecast - 100}%` }} /></div><div className="meter-labels"><span>Low</span><span>High</span></div></div><div className="stat-card"><div className="stat-top"><span>Model confidence</span><span className="confidence-dot" /></div><div className="stat-value">89 <small>%</small></div><div className="stat-delta neutral">Stable <em>7-day horizon</em></div><div className="confidence-row"><span>PM10 (live)</span><b>{liveAqi?.pm10 ?? '—'} µg/m³</b></div></div></section>
        <section className="content-grid"><div className="glass-card chart-card"><div className="section-heading"><div><span className="eyebrow">PREDICTION OUTLOOK</span><h2>AQI trend & forecast</h2><p>Baseline projection from the uploaded dataset. Live API readings appear in the current AQI card.</p></div><div className="segmented">{['24 hours', '7 days', '30 days'].map((item) => <button key={item} className={range === item ? 'active' : ''} onClick={() => setRange(item)}>{item}</button>)}</div></div><div className="chart-legend"><span><i className="legend-history" /> Observed</span><span><i className="legend-forecast" /> Baseline projection</span><span><i className="legend-band" /> Confidence band</span><span className="chart-source">US AQI scale</span></div><ForecastChart /><div className="forecast-days">{forecastDays.map((day, index) => <div key={day}><span>{day}</span><b>{forecast[index]}</b><small className={forecast[index] > 150 ? 'risk-text' : ''}>{forecast[index] > 150 ? 'Spike risk' : 'Moderate'}</small></div>)}</div></div><Alerts onView={() => setActive('Alerts')} /></section>
        <section className="bottom-grid"><div className="glass-card table-card"><div className="section-heading"><div><span className="eyebrow">SOURCE DATA</span><h2>Recent observations</h2></div><button className="text-button" onClick={() => setActive('Data sources')}>View data source <Icon name="arrow" size={15} /></button></div><div className="table-scroll"><table><thead><tr><th>Date</th><th>AQI</th><th>Category</th><th>Primary pollutant</th></tr></thead><tbody>{(showAll ? [...observations, ...observations] : observations).map((row, index) => <tr key={`${row[0]}-${index}`}><td>{row[0]}</td><td><b>{row[1]}</b></td><td><span className={`category ${index < 2 ? 'orange' : 'yellow'}`} />{row[2]}</td><td>{row[3]}</td></tr>)}</tbody></table></div><button className="load-more" onClick={() => setShowAll(!showAll)}>{showAll ? 'Show less' : 'Load more observations'}</button></div><div className="glass-card provenance-card"><div className="section-heading"><div><span className="eyebrow">MODEL STATUS</span><h2>Where is the model?</h2></div></div><div className="model-explanation"><span className="model-state">DEMO PROJECTION</span><p><b>Live model:</b> not connected yet.</p><p>AAAM currently uses a transparent baseline projection from the uploaded AQI series for the 7-day chart and spike alert. The current AQI card is real-time Open-Meteo data.</p><p className="next-model">Production next step: train Prophet, LightGBM, or XGBoost on the full workbook and serve it from an API.</p></div><div className="model-footer"><span className="status-dot" /> Open-Meteo live feed <span>•</span> Baseline v0.1</div></div></section></>}
      {toast && <div className="toast"><span className="status-dot" /> {toast}</div>}
    </main>
  </div>
}

function Alerts({ onView }) {
  return <div className="glass-card alerts-card"><div className="section-heading"><div><span className="eyebrow">AUTOMATED DETECTION</span><h2>Active alerts</h2></div><span className="count-badge">3 active</span></div><div className="alert-list"><div className="alert-item critical"><span className="alert-severity">!</span><div><b>Weekend AQI spike</b><p>Sat 19 Sep · 72% probability above 150</p><small>Detected 8 minutes ago</small></div><span className="item-menu">•••</span></div><div className="alert-item warning"><span className="alert-severity">↗</span><div><b>PM2.5 rising faster</b><p>+18% in the last 6 hours</p><small>Detected 42 minutes ago</small></div><span className="item-menu">•••</span></div><div className="alert-item info"><span className="alert-severity">i</span><div><b>Forecast updated</b><p>New observations improved confidence to 89%</p><small>Detected 1 hour ago</small></div><span className="item-menu">•••</span></div></div><button className="text-button" onClick={onView}>View all alerts <Icon name="arrow" size={15} /></button></div>
}

function Module({ active, onBack, notify }) {
  const tools = [['P', 'Prophet', 'Seasonality-first forecasting'], ['L', 'LightGBM', 'Fast gradient boosting'], ['X', 'XGBoost', 'Spike classification'], ['D', 'Darts', 'Deep time series toolkit'], ['E', 'Evidently', 'Data quality monitoring'], ['M', 'MLflow', 'Experiment tracking']]
  return <section className="subpage glass-card"><div className="section-heading"><div><span className="eyebrow">MODULE</span><h2>{active}</h2><p>Connected to the <b>AAAM AQI Dataset</b> and ready for production data.</p></div><button className="primary-button" onClick={() => notify('Module refreshed.')}>Refresh module</button></div>{active === 'Open-source toolkit' ? <div className="toolkit-grid">{tools.map(([letter, name, description]) => <div className="tool-card" key={name}><span className="tool-icon">{letter}</span><div><b>{name}</b><p>{description}</p></div><span className="open-pill">Open source</span></div>)}</div> : <div className="empty-module"><div className="empty-icon"><Icon name={active === 'Alerts' ? 'bell' : active === 'Forecasts' ? 'chart' : 'database'} size={28} /></div><h3>{active === 'Alerts' ? '3 active signals' : active === 'Forecasts' ? 'Forecast workspace' : 'One connected source'}</h3><p>Use the overview to inspect the current model output, confidence band, and alert rationale.</p><button className="text-button" onClick={onBack}>Back to overview <Icon name="arrow" size={15} /></button></div>}</section>
}

export default App
