import { mockAnalysis } from '../mockData';

function AlertScreen() {
  const risk = mockAnalysis.final_risk_score;
  const level = risk > 0.7 ? "HIGH RISK" : risk > 0.4 ? "CAUTION" : "SAFE";
  const color = risk > 0.7 ? "bg-red-500" : risk > 0.4 ? "bg-yellow-500" : "bg-green-500";

  return (
    <div className="p-6">
      <div className={`${color} text-white p-4 rounded-lg mb-4`}>
        <h1 className="text-2xl font-bold">{level}</h1>
        <p>Risk Score: {risk}</p>
      </div>
      <p className="mb-2"><strong>Transcript:</strong> {mockAnalysis.transcript}</p>
      <p className="mb-2"><strong>Flags:</strong> {mockAnalysis.flags.join(', ')}</p>
      {mockAnalysis.challenge_triggered && (
        <p className="text-orange-600 font-semibold">Challenge triggered — waiting for response...</p>
      )}
    </div>
  );
}

export default AlertScreen;