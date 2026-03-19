import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Chat from './pages/Chat'
import TaxCalculator from './pages/TaxCalculator'
import DocumentEntry from './pages/DocumentEntry'
import Scenarios from './pages/Scenarios'
import Profile from './pages/Profile'

function App() {
  return (
    <div className="flex min-h-screen bg-white">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Chat />} />
          <Route path="/calculator" element={<TaxCalculator />} />
          <Route path="/documents" element={<DocumentEntry />} />
          <Route path="/scenarios" element={<Scenarios />} />
          <Route path="/profile" element={<Profile />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
