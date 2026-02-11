import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { Recordings } from './pages/Recordings'
import { RecordingDetail } from './pages/RecordingDetail'
import { SearchPage } from './pages/Search'
import { Pipeline } from './pages/Pipeline'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/recordings" element={<Recordings />} />
          <Route path="/recordings/:id" element={<RecordingDetail />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/pipeline" element={<Pipeline />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
