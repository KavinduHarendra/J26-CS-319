import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import ThreatSimulation from './pages/ThreatSimulation'
import Evaluate from './pages/Evaluate'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Evaluate />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/threat-simulation" element={<ThreatSimulation />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
