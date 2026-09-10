import { useCallback, useEffect, useRef, useState } from 'react'

export function useRecorder(onComplete) {
  const [state, setState] = useState('idle')
  const [error, setError] = useState(null)
  const [seconds, setSeconds] = useState(0)
  const [stream, setStream] = useState(null)
  const recording = useRef(null)
  const streamRef = useRef(null)
  const callback = useRef(onComplete)
  const mounted = useRef(true)
  const generation = useRef(0)
  const timer = useRef(null)
  useEffect(() => { callback.current = onComplete }, [onComplete])
  const release = useCallback(() => {
    clearInterval(timer.current)
    streamRef.current?.getTracks().forEach(track => track.stop())
    streamRef.current = null
    if (mounted.current) setStream(null)
  }, [])
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      if (recording.current) { recording.current.onstop = null; recording.current.ondataavailable = null; if (recording.current.state !== 'inactive') recording.current.stop() }
      release()
    }
  }, [release])
  const start = useCallback(async () => {
    if (streamRef.current) return
    const token = ++generation.current
    setError(null); setState('requesting')
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw new Error('Recording is unavailable in this browser. Upload an audio file instead.')
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!mounted.current || token !== generation.current) { stream.getTracks().forEach(t => t.stop()); return }
      streamRef.current = stream
      setStream(stream)
      const mimeType = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus'].find(type => MediaRecorder.isTypeSupported(type))
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      recording.current = recorder
      const chunks = []
      recorder.ondataavailable = e => { if (e.data.size) chunks.push(e.data) }
      recorder.onstop = () => {
        release()
        if (mounted.current && token === generation.current) { setState('idle'); callback.current(new Blob(chunks, { type: recorder.mimeType })) }
      }
      recorder.onerror = () => { recorder.onstop = null; if (recorder.state !== 'inactive') recorder.stop(); release(); setState('idle'); setError('Recording was interrupted. Please try again.') }
      recorder.start(); setState('recording'); setSeconds(0)
      const started = performance.now()
      timer.current = setInterval(() => {
        const elapsed = Math.floor((performance.now() - started) / 1000)
        setSeconds(elapsed)
        if (elapsed >= 60 && recorder.state === 'recording') recorder.stop()
      }, 250)
    } catch (err) {
      release()
      if (mounted.current && token === generation.current) { setState('idle'); setError(err.name === 'NotAllowedError' ? 'Microphone permission was denied. Allow access or upload a recording.' : err.message) }
    }
  }, [release])
  const stop = useCallback(() => { if (recording.current?.state === 'recording') recording.current.stop() }, [])
  return { state, error, seconds, stream, start, stop }
}
