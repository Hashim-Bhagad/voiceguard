import { mockAnalysis } from '../mockData';

function MonitoringScreen() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">Live Monitoring</h1>
      <div className="mb-2">
        <p>Acoustic Risk: {mockAnalysis.acoustic_risk_score}</p>
        <div className="w-full bg-gray-200 rounded h-4">
          <div
            className="bg-blue-500 h-4 rounded"
            style={{ width: `${mockAnalysis.acoustic_risk_score * 100}%` }}
          ></div>
        </div>
      </div>
      <div className="mb-2">
        <p>Linguistic Risk: {mockAnalysis.linguistic_risk_score}</p>
        <div className="w-full bg-gray-200 rounded h-4">
          <div
            className="bg-purple-500 h-4 rounded"
            style={{ width: `${mockAnalysis.linguistic_risk_score * 100}%` }}
          ></div>
        </div>
      </div>
      <p className="text-gray-500 italic mt-4">(waveform placeholder goes here)</p>
    </div>
  );
}

export default MonitoringScreen;