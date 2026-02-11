import { useCallback, useState } from 'react'
import { Upload, X, FileAudio } from 'lucide-react'
import { api } from '../api/client'

interface FileUploaderProps {
  onUploaded?: () => void
}

export function FileUploader({ onUploaded }: FileUploaderProps) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [error, setError] = useState<string | null>(null)

  const handleFiles = useCallback((fileList: FileList) => {
    const wavFiles = Array.from(fileList).filter(
      (f) => f.name.endsWith('.wav') || f.type === 'audio/wav' || f.type === 'audio/x-wav'
    )
    if (wavFiles.length === 0) {
      setError('Proszę wybrać pliki WAV')
      return
    }
    setError(null)
    setFiles((prev) => [...prev, ...wavFiles])
  }, [])

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx))
  }

  const uploadAll = async () => {
    setUploading(true)
    setError(null)
    try {
      for (const file of files) {
        await api.uploadRecording(file)
      }
      setFiles([])
      onUploaded?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Błąd przesyłania')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="space-y-3">
      <div
        className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer
          ${dragging ? 'border-blue-500 bg-blue-500/10' : 'border-zinc-700 hover:border-zinc-500'}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files) }}
        onClick={() => {
          const input = document.createElement('input')
          input.type = 'file'
          input.multiple = true
          input.accept = '.wav,audio/wav'
          input.onchange = () => { if (input.files) handleFiles(input.files) }
          input.click()
        }}
      >
        <Upload className="w-8 h-8 mx-auto mb-2 text-zinc-500" />
        <p className="text-sm text-zinc-400">
          Przeciągnij pliki WAV tutaj lub <span className="text-blue-400">kliknij, aby wybrać</span>
        </p>
      </div>

      {files.length > 0 && (
        <div className="space-y-2">
          {files.map((f, i) => (
            <div key={i} className="flex items-center gap-2 bg-zinc-900 rounded-lg px-3 py-2 text-sm">
              <FileAudio className="w-4 h-4 text-zinc-400" />
              <span className="flex-1 truncate">{f.name}</span>
              <span className="text-zinc-500">{(f.size / 1024 / 1024).toFixed(1)} MB</span>
              <button onClick={(e) => { e.stopPropagation(); removeFile(i) }} className="text-zinc-500 hover:text-red-400">
                <X className="w-4 h-4" />
              </button>
            </div>
          ))}
          <button
            onClick={uploadAll}
            disabled={uploading}
            className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg text-sm font-medium transition-colors"
          >
            {uploading ? 'Przesyłanie...' : `Prześlij ${files.length} plik(ów)`}
          </button>
        </div>
      )}

      {error && <p className="text-sm text-red-400">{error}</p>}
    </div>
  )
}
