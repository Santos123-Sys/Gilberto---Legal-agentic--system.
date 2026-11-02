import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import { AuthGate } from './auth/AuthGate.jsx'
import { AppErrorBoundary } from './components/AppErrorBoundary.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <AuthGate><App /></AuthGate>
    </AppErrorBoundary>
  </React.StrictMode>,
)
