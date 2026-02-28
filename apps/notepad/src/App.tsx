import { useState, useEffect, useCallback } from 'react'
import './App.css'

const STORAGE_KEY = 'notepad-content'

function App() {
  const [content, setContent] = useState(() => {
    return localStorage.getItem(STORAGE_KEY) ?? ''
  })
  const [saved, setSaved] = useState(true)

  const save = useCallback(() => {
    localStorage.setItem(STORAGE_KEY, content)
    setSaved(true)
  }, [content])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        save()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [save])

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setContent(e.target.value)
    setSaved(false)
  }

  return (
    <div className="notepad">
      <header className="notepad-header">
        <h1>Notepad</h1>
        <div className="notepad-actions">
          <span className={`save-status ${saved ? 'saved' : 'unsaved'}`}>
            {saved ? 'Saved' : 'Unsaved'}
          </span>
          <button onClick={save} disabled={saved}>
            Save
          </button>
        </div>
      </header>
      <textarea
        className="notepad-editor"
        value={content}
        onChange={handleChange}
        placeholder="Start typing..."
        autoFocus
      />
    </div>
  )
}

export default App
