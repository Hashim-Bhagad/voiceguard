// PLACEHOLDER: this hook stands in for the real backend integration point.
// Once the backend exposes POST /analyze, this file should be updated to call
// it (e.g. via fetch) and return the live response in the same shape below.
// Every component that displays analysis data MUST call useAnalysis() rather
// than hardcoding its own values, so the eventual swap to real data only
// requires changing this one file.

const MOCK_ANALYSIS = {
  acoustic_risk_score: 0.62,
  linguistic_risk_score: 0.48,
  final_risk_score: 0.57,
  transcript:
    "Hi, this is Alex calling from your bank's security department. We've detected unusual activity on your account and need to verify your identity right away. Can you confirm your card number and the security code on the back?",
  flags: [
    "urgency_language",
    "impersonation_bank_official",
    "request_for_sensitive_info",
    "synthetic_voice_artifacts",
  ],
  challenge_triggered: true,
};

export function useAnalysis() {
  return MOCK_ANALYSIS;
}
