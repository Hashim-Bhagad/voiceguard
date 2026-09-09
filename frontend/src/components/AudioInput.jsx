import { useRef, useState } from 'react'
import { useAnalysis } from '../lib/AnalysisContext'

export default function AudioInput() {
  const { status, runAnalysis, reset } = useAnalysis()
  const fileInputRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const [isRecording, setIsRecording] = useState(false)
  const [micError, setMicError] = useState(null)
  const [fileName, setFileName] = useState(null)

  function handleFileChange(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setFileName(file.name)
    runAnalysis(file)
  }

  async function startRecording() {
    setMicError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (e) => chunksRef.current.push(e.data)
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        stream.getTracks().forEach((t) => t.stop())
        setFileName('mic-recording.webm')
        runAnalysis(blob)
      }
      recorder.start()
      mediaRecorderRef.current = recorder
      setIsRecording(true)
    } catch {
      setMicError('Microphone access denied or unavailable. Try uploading a file instead.')
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop()
    setIsRecording(false)
  }

  if (status === 'analyzing') {
    return (
      <div className="dash-card">
        <span className="dash-status-pill" role="status">
          <span className="dash-dot-pulse" />
          Analyzing {fileName ? `"${fileName}"` : 'audio'}…
        </span>
      </div>
    )
  }

  if (status === 'complete') {
    return (
      <div className="dash-card dash-complete">
        <span>Analysis complete for {fileName ? `"${fileName}"` : 'this call'}.</span>
        <button onClick={reset}>Analyze another call</button>
      </div>
    )
  }

  return (
    <div className="dash-card">
      <h3>Start a call analysis</h3>
      <div className="dash-actions">
        <button disabled={isRecording} onClick={() => fileInputRef.current?.click()}>Upload recording</button>
        <input ref={fileInputRef} type="file" aria-label="Upload audio recording" accept="audio/*" onChange={handleFileChange} style={{ display: 'none' }} />

        {!isRecording ? (
          <button onClick={startRecording}>Record from mic</button>
        ) : (
          <button onClick={stopRecording}>Stop recording</button>
        )}

        <button disabled={isRecording} onClick={() => runAnalysis('demo-sample.wav')}>Use sample call (demo)</button>
      </div>
      {micError && <p style={{ color: '#f2545b', fontSize: 12, marginTop: 12 }}>{micError}</p>}
    </div>
  )
}
