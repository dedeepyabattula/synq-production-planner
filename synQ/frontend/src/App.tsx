import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import FactoryBuilder from './pages/FactoryBuilder';
import ProductionSchedule from './pages/ProductionSchedule';
import DisruptionSimulator from './pages/DisruptionSimulator';
import RecoveryCenter from './pages/RecoveryCenter';
import ApprovalCenter from './pages/ApprovalCenter';
import History from './pages/History';
import { useState, useEffect } from 'react';
import { factoryService } from './api';
import { Factory } from './types';

function App() {
  const [currentFactory, setCurrentFactory] = useState<Factory | null>(null);

  // Load a default factory on mount
  useEffect(() => {
    factoryService.getFactories().then(factories => {
      if (factories.length > 0) {
        // Choose EV Battery Plant if available
        const evFactory = factories.find(f => f.name === 'EV Battery Plant');
        setCurrentFactory(evFactory || factories[0]);
      }
    }).catch(err => console.error("Could not load factories", err));
  }, []);

  return (
    <Router>
      <Layout factory={currentFactory} onFactoryChange={setCurrentFactory}>
        {currentFactory ? (
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard factoryId={currentFactory.id} />} />
            <Route path="/factory-builder" element={<FactoryBuilder factoryId={currentFactory.id} onFactoryCreated={setCurrentFactory} />} />
            <Route path="/factory-builder/new" element={<FactoryBuilder factoryId={currentFactory.id} createMode onFactoryCreated={setCurrentFactory} />} />
            <Route path="/schedule" element={<ProductionSchedule factoryId={currentFactory.id} />} />
            <Route path="/disruption" element={<DisruptionSimulator factoryId={currentFactory.id} />} />
            <Route path="/recovery" element={<RecoveryCenter factoryId={currentFactory.id} />} />
            <Route path="/approval" element={<ApprovalCenter factoryId={currentFactory.id} />} />
            <Route path="/history" element={<History factoryId={currentFactory.id} />} />
          </Routes>
        ) : (
          <div className="flex h-screen items-center justify-center bg-synq-dark text-synq-text">
            <p className="animate-pulse">Loading Factory Database...</p>
          </div>
        )}
      </Layout>
    </Router>
  );
}

export default App;
