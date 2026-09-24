import { useEffect, useState } from 'react'
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
  'Ariyalur, IN': { latitude: 11.1401, longitude: 79.0786 },
  'Chengalpattu, IN': { latitude: 12.6819, longitude: 79.9888 },
  'Coimbatore, IN': { latitude: 11.0168, longitude: 76.9558 },
  'Cuddalore, IN': { latitude: 11.7480, longitude: 79.7714 },
  'Dharmapuri, IN': { latitude: 12.1211, longitude: 78.1582 },
  'Dindigul, IN': { latitude: 10.3673, longitude: 77.9803 },
  'Erode, IN': { latitude: 11.3410, longitude: 77.7172 },
  'Kallakurichi, IN': { latitude: 11.7401, longitude: 78.9597 },
  'Kancheepuram, IN': { latitude: 12.8342, longitude: 79.7036 },
  'Karur, IN': { latitude: 10.9601, longitude: 78.0766 },
  'Krishnagiri, IN': { latitude: 12.5186, longitude: 78.2137 },
  'Madurai, IN': { latitude: 9.9252, longitude: 78.1198 },
  'Mayiladuthurai, IN': { latitude: 11.1035, longitude: 79.6550 },
  'Nagapattinam, IN': { latitude: 10.7672, longitude: 79.8449 },
  'Nagercoil, IN': { latitude: 8.1833, longitude: 77.4119 },
  'Namakkal, IN': { latitude: 11.2194, longitude: 78.1677 },
  'Perambalur, IN': { latitude: 11.2320, longitude: 78.8801 },
  'Pudukkottai, IN': { latitude: 10.3797, longitude: 78.8208 },
  'Ramanathapuram, IN': { latitude: 9.3639, longitude: 78.8395 },
  'Ranipet, IN': { latitude: 12.9249, longitude: 79.3333 },
  'Salem, IN': { latitude: 11.6643, longitude: 78.1460 },
  'Sivaganga, IN': { latitude: 9.8433, longitude: 78.4809 },
  'Tenkasi, IN': { latitude: 8.9590, longitude: 77.3152 },
  'Thanjavur, IN': { latitude: 10.7870, longitude: 79.1378 },
  'Theni, IN': { latitude: 10.0104, longitude: 77.4768 },
  'Thoothukudi, IN': { latitude: 8.7642, longitude: 78.1348 },
  'Tiruchirappalli, IN': { latitude: 10.7905, longitude: 78.7047 },
  'Tirunelveli, IN': { latitude: 8.7139, longitude: 77.7567 },
  'Tirupathur, IN': { latitude: 12.4970, longitude: 78.5680 },
  'Tiruppur, IN': { latitude: 11.1085, longitude: 77.3411 },
  'Tiruvallur, IN': { latitude: 13.1439, longitude: 79.9080 },
  'Tiruvannamalai, IN': { latitude: 12.2253, longitude: 79.0747 },
  'Tiruvarur, IN': { latitude: 10.7725, longitude: 79.6368 },
  'Vellore, IN': { latitude: 12.9165, longitude: 79.1325 },
  'Viluppuram, IN': { latitude: 11.9401, longitude: 79.4861 },
  'Virudhunagar, IN': { latitude: 9.5851, longitude: 77.9579 },
  'Washington, US': { latitude: 38.9072, longitude: -77.0369 },
  'Moscow, RU': { latitude: 55.7558, longitude: 37.6173 },
  'Russia (national view)': { latitude: 55.7558, longitude: 37.6173 },
}
const tamilNaduSources = Object.keys(locations).filter((name) => name.endsWith(', IN')).map((name) => ({
  value: `${name.split(',')[0].toLowerCase().replaceAll(' ', '-')}-api`,
  label: `${name.split(',')[0]} API`,
  location: name,
}))

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

function ForecastChart({ values }) {
  const point = (value, index) => `${index * 3.1 + 3},${106 - value * 0.55}`
  const observedPoints = observed.map(point).join(' ')
  const forecastPoints = values.map((value, index) => `${90 + index * 3.1},${106 - value * 0.55}`).join(' ')
  return <div className="chart-wrap">
    <svg viewBox="0 0 112 115" preserveAspectRatio="none" className="aqi-chart">
      <defs><linearGradient id="chart-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#ed795d" stopOpacity=".28" /><stop offset="100%" stopColor="#ed795d" stopOpacity="0" /></linearGradient></defs>
      {[25, 50, 75, 100].map((y) => <line key={y} x1="3" x2="109" y1={y} y2={y} className="chart-grid" />)}
      <path d={`M 3,106 L ${observedPoints} L 90,106 Z`} fill="url(#chart-fill)" />
      <polyline points={observedPoints} className="history-line" />
      <line x1="90" x2="90" y1="10" y2="106" className="today-line" />
      <polyline points={forecastPoints} className="forecast-line" />
      {values.map((value, index) => <circle key={`${value}-${index}`} cx={90 + index * 3.1} cy={106 - value * 0.55} r="1.5" className="forecast-dot" />)}
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
  const [modelForecast, setModelForecast] = useState(null)
  const [modelStatus, setModelStatus] = useState('Connecting to AAAM model…')
  const [modelSpikeProbability, setModelSpikeProbability] = useState(null)
  const [inputSource, setInputSource] = useState('api')
  const [sourceChoice, setSourceChoice] = useState('chennai-api')
  const [hardwareDevice, setHardwareDevice] = useState(null)
  const currentForecast = modelForecast ?? forecast
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
  useEffect(() => {
    fetch('/api/source')
      .then((response) => response.json())
      .then((data) => {
        setInputSource(data.source)
        setHardwareDevice(data.device_id)
        if (data.source === 'hardware') setSourceChoice('hardware')
      })
      .catch(() => setModelStatus('AAAM API unavailable'))
  }, [])
  useEffect(() => {
    const coordinates = locations[location]
    const controller = new AbortController()
    fetch('/api/forecast', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...coordinates, horizon: 7 }),
      signal: controller.signal,
    })
      .then((response) => response.ok ? response.json() : response.json().then((body) => Promise.reject(new Error(body.detail?.message ?? 'Model unavailable'))))
      .then((data) => {
        setModelForecast(data.forecast)
        setModelSpikeProbability(Math.round(data.spike_probability * 100))
        setModelStatus(`Chronos-2 live · ${new Date(data.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`)
      })
      .catch((error) => {
        if (error.name !== 'AbortError') {
          setModelForecast(null)
          setModelSpikeProbability(null)
          setModelStatus('Model unavailable · baseline hidden from alerts')
        }
      })
    return () => controller.abort()
  }, [location])
  const notify = (message) => {
    setToast(message)
    window.setTimeout(() => setToast(''), 2600)
  }
  const switchInputSource = (source) => {
    setModelStatus(source === 'hardware' ? 'Switching to hardware…' : 'Switching to city API…')
    fetch('/api/source', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source, device_id: source === 'hardware' ? hardwareDevice : null }),
    })
      .then((response) => response.ok ? response.json() : response.json().then((body) => Promise.reject(new Error(body.detail ?? 'Source switch failed'))))
      .then((data) => {
        setInputSource(data.source)
        setModelForecast(null)
        setModelSpikeProbability(null)
        setModelStatus(source === 'hardware' ? `Hardware input · ${data.device_id}` : 'Running Chronos-2 from city API…')
      })
      .catch((error) => setModelStatus(error.message))
  }
  const selectDataSource = (choice) => {
    setSourceChoice(choice)
    if (choice === 'hardware') {
      switchInputSource('hardware')
      return
    }
    const selectedSource = tamilNaduSources.find((source) => source.value === choice)
    const nextLocation = selectedSource?.location ?? location
    if (nextLocation !== location) {
      setLocation(nextLocation)
      setLiveStatus('Updating live reading…')
      setLiveAqi(null)
      setModelForecast(null)
      setModelSpikeProbability(null)
    }
    switchInputSource('api')
  }

  const navItems = [['Overview', 'grid'], ['Forecasts', 'chart'], ['Alerts', 'bell'], ['Data sources', 'database'], ['Open-source toolkit', 'settings']]
  return <div className="shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark"><span /></div><div><strong>AAAM</strong><small>Air intelligence</small></div></div>
      <div className="workspace"><span className="workspace-dot" /> AAAM AQI Dataset <span className="chevron">⌄</span></div>
      <p className="nav-label">Workspace</p>
      <nav>{navItems.map(([label, icon]) => <button key={label} className={`nav-item ${active === label ? 'selected' : ''}`} onClick={() => setActive(label)}><Icon name={icon} /> {label}{label === 'Alerts' && <span className="nav-badge">3</span>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="model-status"><span className={`status-dot ${modelForecast ? '' : 'pulse'}`} /><div><b>{modelForecast ? 'Chronos-2 online' : 'Model starting'}</b><small>{modelForecast ? 'Forecasts enabled' : 'Alerts paused'}</small></div></div><button className="user-card" onClick={() => notify('Profile settings are coming soon.')}><span className="avatar">AK</span><span><b>Arjun Kumar</b><small>Administrator</small></span><span className="more">•••</span></button></div>
    </aside>
    <main className="main">
      <header className="topbar"><div><div className="eyebrow">AAAM / AIR QUALITY / LIVE MONITORING</div><h1>{active === 'Overview' ? 'Good morning, buddy' : active}</h1><div className="live-status"><span className={`status-dot ${liveAqi ? '' : 'pulse'}`} /> {liveStatus}<span className={`status-dot model-status-dot ${modelForecast ? '' : 'pulse'}`} /> {modelStatus}</div></div><div className="header-actions"><label className="source-selector"><span>Data source</span><select value={sourceChoice} onChange={(event) => selectDataSource(event.target.value)} aria-label="Select AQI data source"><option value="hardware">Hardware{hardwareDevice ? ` · ${hardwareDevice}` : ' · send telemetry first'}</option><optgroup label="Tamil Nadu district APIs">{tamilNaduSources.map((source) => <option key={source.value} value={source.value}>{source.label}</option>)}</optgroup><option value="api">Selected city API</option></select></label><label className="location"><span>⌖</span><select value={location} onChange={(event) => { const nextLocation = event.target.value; setLocation(nextLocation); const matchingSource = tamilNaduSources.find((source) => source.location === nextLocation); setSourceChoice(matchingSource?.value ?? 'api'); setLiveStatus('Updating live reading…'); setLiveAqi(null); setModelStatus('Running Chronos-2…'); setModelForecast(null); setModelSpikeProbability(null) }}>{Object.keys(locations).map((name) => <option key={name}>{name}</option>)}</select></label><button className={`icon-button ${notifications ? 'has-alert' : ''}`} onClick={() => setNotifications(!notifications)} aria-label="Toggle notifications"><Icon name="bell" /></button><button className="primary-button" onClick={() => notify('Forecast refreshed using the latest uploaded data.')}><Icon name="upload" size={16} /> Update data</button></div></header>
      {inputSource !== 'hardware' && <p className="source-note">Chennai API and Salem API use Open-Meteo live AQI data; no API key is required. Hardware mode accepts your device telemetry.</p>}
      {active !== 'Overview' ? <Module active={active} onBack={() => setActive('Overview')} notify={notify} /> : <><section className="alert-banner"><div className="alert-icon"><Icon name="bell" /></div><div><b>{modelForecast ? 'Elevated AQI expected this weekend' : 'Spike alerts are paused'}</b><p>{modelForecast ? <>Chronos-2 detects a <strong>{modelSpikeProbability}% probability</strong> of a spike above 150 between Sat 19 – Sun 20 Sep.</> : 'AAAM is waiting for the Chronos-2 backend. Baseline values will not trigger purifier commands.'}</p></div><button onClick={() => setActive('Alerts')}>View status <Icon name="arrow" size={15} /></button><span className="dismiss" onClick={(event) => event.currentTarget.parentElement.remove()}>×</span></section>
        <section className="stat-grid"><div className="stat-card"><div className="stat-top"><span>Current AQI</span><span className="status-pill moderate">Live</span></div><div className="stat-value">{liveAqi?.value ?? 124} <small>US AQI</small></div><div className="stat-delta down">PM2.5 {liveAqi?.pm25 ?? '—'} µg/m³ <em>real-time</em></div><div className="mini-bars">{[40, 55, 44, 71, 58, 64, 49, 68, 62, 55, 48, 53].map((height, i) => <i key={i} style={{ height: `${height}%` }} />)}</div></div><div className="stat-card"><div className="stat-top"><span>Next 7-day avg.</span><span className="trend-up">↗</span></div><div className="stat-value">{Math.round(currentForecast.reduce((sum, value) => sum + value, 0) / currentForecast.length)} <small>US AQI</small></div><div className="stat-delta up">{modelForecast ? 'Chronos-2' : 'Waiting for model'} <em>{modelForecast ? 'live forecast' : 'not a model result'}</em></div><div className="sparkline"><svg viewBox="0 0 150 35" preserveAspectRatio="none"><polyline points="0,28 16,25 30,27 45,20 59,22 72,14 88,18 103,9 116,13 132,5 150,8" /></svg></div></div><div className="stat-card"><div className="stat-top"><span>Spike likelihood</span><span className={`status-pill ${modelForecast ? 'high' : 'moderate'}`}>{modelForecast ? 'Model risk' : 'Waiting'}</span></div><div className="stat-value">{modelSpikeProbability ?? '—'} <small>%</small></div><div className="stat-delta up">{modelForecast ? 'Chronos-2 probability' : 'No alert generated'} <em>threshold &gt;150</em></div><div className="risk-meter"><span style={{ width: `${modelSpikeProbability ?? 0}%` }} /></div><div className="meter-labels"><span>Low</span><span>High</span></div></div><div className="stat-card"><div className="stat-top"><span>Model confidence</span><span className="confidence-dot" /></div><div className="stat-value">{modelForecast ? 89 : '—'} <small>{modelForecast ? '%' : ''}</small></div><div className="stat-delta neutral">{modelForecast ? 'Chronos-2 ready' : 'Model offline'} <em>7-day horizon</em></div><div className="confidence-row"><span>PM10 (live)</span><b>{liveAqi?.pm10 ?? '—'} µg/m³</b></div></div></section>
        <section className="content-grid"><div className="glass-card chart-card"><div className="section-heading"><div><span className="eyebrow">PREDICTION OUTLOOK</span><h2>AQI trend & forecast</h2><p>{modelForecast ? 'Chronos-2 forecast from live AQI history.' : 'Waiting for Chronos-2 backend; no forecast alert is active.'}</p></div><div className="segmented">{['24 hours', '7 days', '30 days'].map((item) => <button key={item} className={range === item ? 'active' : ''} onClick={() => setRange(item)}>{item}</button>)}</div></div><div className="chart-legend"><span><i className="legend-history" /> Observed</span><span><i className="legend-forecast" /> {modelForecast ? 'Chronos-2' : 'Awaiting model'}</span><span><i className="legend-band" /> Confidence band</span><span className="chart-source">US AQI scale</span></div><ForecastChart values={currentForecast} /><div className="forecast-days">{forecastDays.map((day, index) => <div key={day}><span>{day}</span><b>{currentForecast[index]}</b><small className={modelForecast && currentForecast[index] > 150 ? 'risk-text' : ''}>{modelForecast && currentForecast[index] > 150 ? 'Spike risk' : modelForecast ? 'Forecast' : 'Pending'}</small></div>)}</div></div><Alerts modelReady={Boolean(modelForecast)} spikeProbability={modelSpikeProbability} onView={() => setActive('Alerts')} /></section>
        <section className="bottom-grid"><div className="glass-card table-card"><div className="section-heading"><div><span className="eyebrow">SOURCE DATA</span><h2>Recent observations</h2></div><button className="text-button" onClick={() => setActive('Data sources')}>View data source <Icon name="arrow" size={15} /></button></div><div className="table-scroll"><table><thead><tr><th>Date</th><th>AQI</th><th>Category</th><th>Primary pollutant</th></tr></thead><tbody>{(showAll ? [...observations, ...observations] : observations).map((row, index) => <tr key={`${row[0]}-${index}`}><td>{row[0]}</td><td><b>{row[1]}</b></td><td><span className={`category ${index < 2 ? 'orange' : 'yellow'}`} />{row[2]}</td><td>{row[3]}</td></tr>)}</tbody></table></div><button className="load-more" onClick={() => setShowAll(!showAll)}>{showAll ? 'Show less' : 'Load more observations'}</button></div><div className="glass-card provenance-card"><div className="section-heading"><div><span className="eyebrow">MODEL STATUS</span><h2>Where is the model?</h2></div></div><div className="model-explanation"><span className={`model-state ${modelForecast ? 'model-ready' : ''}`}>{modelForecast ? 'CHRONOS-2 CONNECTED' : 'MODEL STARTING'}</span><p><b>Backend:</b> {modelStatus}</p><p>{modelForecast ? 'The forecast is generated by Chronos-2 from the latest 14 days of live hourly AQI history.' : 'AAAM is waiting for the FastAPI service at /api/forecast. The baseline values are visible for layout only and do not trigger alerts.'}</p><p className="next-model">Device path: sensor telemetry → FastAPI → Chronos-2 spike score → MQTT/TLS purifier command.</p></div><div className="model-footer"><span className="status-dot" /> Open-Meteo live feed <span>•</span> {modelForecast ? 'Chronos-2' : 'API required'}</div></div></section></>}
      {toast && <div className="toast"><span className="status-dot" /> {toast}</div>}
    </main>
  </div>
}

function Alerts({ onView, modelReady, spikeProbability }) {
  return <div className="glass-card alerts-card"><div className="section-heading"><div><span className="eyebrow">AUTOMATED DETECTION</span><h2>{modelReady ? 'Active alerts' : 'Alert status'}</h2></div><span className="count-badge">{modelReady ? '3 active' : 'Paused'}</span></div><div className="alert-list"><div className={`alert-item ${modelReady ? 'critical' : 'info'}`}><span className="alert-severity">{modelReady ? '!' : 'i'}</span><div><b>{modelReady ? 'Weekend AQI spike' : 'Chronos-2 unavailable'}</b><p>{modelReady ? `Predicted spike probability ${spikeProbability}% above AQI 150` : 'Start the AAAM API with Chronos-2 to enable spike detection.'}</p><small>{modelReady ? 'Generated from live AQI history' : 'No purifier command will be issued'}</small></div><span className="item-menu">•••</span></div><div className="alert-item warning"><span className="alert-severity">↗</span><div><b>PM2.5 rising faster</b><p>+18% in the last 6 hours</p><small>Observed data signal</small></div><span className="item-menu">•••</span></div><div className="alert-item info"><span className="alert-severity">i</span><div><b>Forecast service</b><p>{modelReady ? 'Forecast updated successfully' : 'Waiting for backend model health'}</p><small>AAAM device safety policy active</small></div><span className="item-menu">•••</span></div></div><button className="text-button" onClick={onView}>View all alerts <Icon name="arrow" size={15} /></button></div>
}

function Module({ active, onBack, notify }) {
  const tools = [['P', 'Prophet', 'Seasonality-first forecasting'], ['L', 'LightGBM', 'Fast gradient boosting'], ['X', 'XGBoost', 'Spike classification'], ['D', 'Darts', 'Deep time series toolkit'], ['E', 'Evidently', 'Data quality monitoring'], ['M', 'MLflow', 'Experiment tracking']]
  return <section className="subpage glass-card"><div className="section-heading"><div><span className="eyebrow">MODULE</span><h2>{active}</h2><p>Connected to the <b>AAAM AQI Dataset</b> and ready for production data.</p></div><button className="primary-button" onClick={() => notify('Module refreshed.')}>Refresh module</button></div>{active === 'Open-source toolkit' ? <div className="toolkit-grid">{tools.map(([letter, name, description]) => <div className="tool-card" key={name}><span className="tool-icon">{letter}</span><div><b>{name}</b><p>{description}</p></div><span className="open-pill">Open source</span></div>)}</div> : <div className="empty-module"><div className="empty-icon"><Icon name={active === 'Alerts' ? 'bell' : active === 'Forecasts' ? 'chart' : 'database'} size={28} /></div><h3>{active === 'Alerts' ? '3 active signals' : active === 'Forecasts' ? 'Forecast workspace' : 'One connected source'}</h3><p>Use the overview to inspect the current model output, confidence band, and alert rationale.</p><button className="text-button" onClick={onBack}>Back to overview <Icon name="arrow" size={15} /></button></div>}</section>
}

export default App
