import { useEffect, useRef, useState, useCallback, useImperativeHandle, forwardRef } from 'react'
import WaveSurfer from 'wavesurfer.js'
import { Play, Pause, SkipBack, SkipForward, Volume2, VolumeX } from 'lucide-react'

export interface AudioPlayerHandle {
  seekTo: (seconds: number) => void
}

interface AudioPlayerProps {
  url: string
  onTimeUpdate?: (time: number) => void
}

export const AudioPlayer = forwardRef<AudioPlayerHandle, AudioPlayerProps>(
  ({ url, onTimeUpdate }, ref) => {
    const containerRef = useRef<HTMLDivElement>(null)
    const wsRef = useRef<WaveSurfer | null>(null)
    const [playing, setPlaying] = useState(false)
    const [currentTime, setCurrentTime] = useState(0)
    const [duration, setDuration] = useState(0)
    const [muted, setMuted] = useState(false)
    const [ready, setReady] = useState(false)

    useEffect(() => {
      if (!containerRef.current) return

      const ws = WaveSurfer.create({
        container: containerRef.current,
        waveColor: '#52525b',
        progressColor: '#3b82f6',
        cursorColor: '#f4f4f5',
        cursorWidth: 1,
        barWidth: 2,
        barGap: 1,
        barRadius: 2,
        height: 64,
        normalize: true,
      })

      ws.load(url)

      ws.on('ready', () => {
        setDuration(ws.getDuration())
        setReady(true)
      })
      ws.on('timeupdate', (t) => {
        setCurrentTime(t)
        onTimeUpdate?.(t)
      })
      ws.on('play', () => setPlaying(true))
      ws.on('pause', () => setPlaying(false))
      ws.on('finish', () => setPlaying(false))

      wsRef.current = ws

      return () => {
        ws.destroy()
        wsRef.current = null
        setReady(false)
      }
    }, [url]) // eslint-disable-line react-hooks/exhaustive-deps

    const seekTo = useCallback((seconds: number) => {
      const ws = wsRef.current
      if (!ws || !ready) return
      const dur = ws.getDuration()
      if (dur > 0) ws.seekTo(seconds / dur)
    }, [ready])

    useImperativeHandle(ref, () => ({ seekTo }), [seekTo])

    const fmt = (s: number) => {
      const m = Math.floor(s / 60)
      const sec = Math.floor(s % 60)
      return `${m}:${sec.toString().padStart(2, '0')}`
    }

    const skip = (delta: number) => {
      const ws = wsRef.current
      if (!ws) return
      ws.setTime(Math.max(0, Math.min(ws.getDuration(), ws.getCurrentTime() + delta)))
    }

    const toggleMute = () => {
      const ws = wsRef.current
      if (!ws) return
      ws.setMuted(!muted)
      setMuted(!muted)
    }

    return (
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
        <div ref={containerRef} className={ready ? '' : 'opacity-30'} />
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1">
            <button onClick={() => skip(-5)} className="p-1.5 hover:bg-zinc-800 rounded-lg transition-colors" title="-5s">
              <SkipBack className="w-4 h-4" />
            </button>
            <button
              onClick={() => wsRef.current?.playPause()}
              disabled={!ready}
              className="p-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-full transition-colors"
            >
              {playing ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
            </button>
            <button onClick={() => skip(5)} className="p-1.5 hover:bg-zinc-800 rounded-lg transition-colors" title="+5s">
              <SkipForward className="w-4 h-4" />
            </button>
          </div>

          <span className="text-sm text-zinc-400 font-mono min-w-[80px]">
            {fmt(currentTime)} / {fmt(duration)}
          </span>

          <div className="flex-1" />

          <button onClick={toggleMute} className="p-1.5 hover:bg-zinc-800 rounded-lg transition-colors">
            {muted ? <VolumeX className="w-4 h-4 text-zinc-500" /> : <Volume2 className="w-4 h-4 text-zinc-400" />}
          </button>
        </div>
      </div>
    )
  }
)
