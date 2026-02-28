import type { Components } from 'react-markdown'
import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './App.css'

async function sha256Hex(message: string): Promise<string> {
  const data = new TextEncoder().encode(message)
  const hashBuffer = await crypto.subtle.digest('SHA-256', data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('')
}

interface ContentItem {
  type: string
  text?: string
  image_url?: string
  filename?: string
  file_data?: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string | ContentItem[]
}

interface Attachment {
  name: string
  type: string
  dataUrl: string
}

const MODELS = [
  'gpt-4o-mini',
  'gpt-4o',
  'gpt-4.1-nano',
  'gpt-4.1-mini',
  'gpt-4.1',
  'o4-mini',
]

function getMessageText(content: string | ContentItem[]): string {
  if (typeof content === 'string') return content
  return content
    .filter((item) => item.type === 'input_text' || item.type === 'output_text')
    .map((item) => item.text ?? '')
    .join('\n')
}

function getMessageAttachments(content: string | ContentItem[]): ContentItem[] {
  if (typeof content === 'string') return []
  return content.filter(
    (item) => item.type === 'input_image' || item.type === 'input_file',
  )
}

function getFileExtLabel(filename: string | undefined): string {
  if (!filename) return 'FILE'
  const ext = filename.split('.').pop()?.toUpperCase()
  return ext ?? 'FILE'
}

const SAFE_URL_SCHEMES = /^https?:\/\//i

function sanitizeHref(href: string | undefined): string | undefined {
  if (!href) return undefined
  if (SAFE_URL_SCHEMES.test(href)) return href
  return undefined
}

/** Sanitize markdown: restrict URL schemes, open links in new tab, block images. */
const markdownComponents: Components = {
  a: ({ href, children }) => {
    const safeHref = sanitizeHref(href)
    if (!safeHref) return <span>{children}</span>
    return (
      <a href={safeHref} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    )
  },
  img: ({ alt }) => <span>[Image: {alt ?? 'blocked'}]</span>,
}

/** Strip base64 file data from older messages to reduce request payload. */
function stripFileData(msgs: Message[]): Message[] {
  return msgs.map((msg, i) => {
    if (i >= msgs.length - 1) return msg
    if (typeof msg.content === 'string') return msg
    const stripped = msg.content.map((item) => {
      if (item.type === 'input_image') {
        return { type: 'input_text', text: '[Image]' }
      }
      if (item.type === 'input_file') {
        return { type: 'input_text', text: `[File: ${item.filename ?? 'unknown'}]` }
      }
      return item
    })
    return { ...msg, content: stripped }
  })
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [isComposing, setIsComposing] = useState(false)
  const [model, setModel] = useState('gpt-4o-mini')
  const [instructions, setInstructions] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files) return
    const MAX_FILE_SIZE = 3.5 * 1024 * 1024 // ~3.5 MB (base64 → ~4.7 MB)
    Array.from(files).forEach((file) => {
      if (file.size > MAX_FILE_SIZE) {
        alert(`${file.name} is too large (max 3.5 MB)`)
        return
      }
      const reader = new FileReader()
      reader.onload = () => {
        setAttachments((prev) => [
          ...prev,
          { name: file.name, type: file.type, dataUrl: reader.result as string },
        ])
      }
      reader.readAsDataURL(file)
    })
    e.target.value = ''
  }

  const removeAttachment = (index: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== index))
  }

  const sendMessage = async () => {
    const text = input.trim()
    if ((!text && attachments.length === 0) || loading) return

    let userContent: string | ContentItem[]
    if (attachments.length === 0) {
      userContent = text
    } else {
      const items: ContentItem[] = []
      if (text) {
        items.push({ type: 'input_text', text })
      }
      for (const att of attachments) {
        if (att.type.startsWith('image/')) {
          items.push({ type: 'input_image', image_url: att.dataUrl })
        } else {
          items.push({ type: 'input_file', filename: att.name, file_data: att.dataUrl })
        }
      }
      userContent = items
    }

    const userMessage: Message = { role: 'user', content: userContent }
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setInput('')
    setAttachments([])
    setLoading(true)

    try {
      const body = JSON.stringify({
        messages: stripFileData(updatedMessages),
        model,
        ...(instructions ? { instructions } : {}),
      })
      const bodyHash = await sha256Hex(body)
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-amz-content-sha256': bodyHash,
        },
        body,
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()
      setMessages([...updatedMessages, { role: 'assistant', content: data.message }])
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error'
      setMessages([
        ...updatedMessages,
        { role: 'assistant', content: `Error: ${errorMessage}` },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !isComposing) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="chat">
      <header className="chat-header">
        <h1>Chat</h1>
        <button
          className="settings-toggle"
          onClick={() => setShowSettings(!showSettings)}
          title="Settings"
          aria-label="Open settings"
        >
          <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      </header>

      {showSettings && (
        <div className="settings-panel">
          <div className="settings-row">
            <label htmlFor="model-select">Model</label>
            <select
              id="model-select"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            >
              {MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div className="settings-row">
            <label htmlFor="instructions-input">System Prompt</label>
            <textarea
              id="instructions-input"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="Enter system prompt..."
              rows={3}
            />
          </div>
        </div>
      )}

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div className="chat-message-role">
              {msg.role === 'user' ? 'You' : 'AI'}
            </div>
            <div className="chat-message-content">
              {msg.role === 'assistant' ? (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  components={markdownComponents}
                >
                  {getMessageText(msg.content)}
                </ReactMarkdown>
              ) : (
                <>
                  {getMessageAttachments(msg.content).map((att, j) => (
                    <div key={j} className="message-attachment">
                      {att.type === 'input_image' && att.image_url ? (
                        <img src={att.image_url} alt="attached" />
                      ) : (
                        <span className="file-badge">{att.filename}</span>
                      )}
                    </div>
                  ))}
                  <span style={{ whiteSpace: 'pre-wrap' }}>
                    {getMessageText(msg.content)}
                  </span>
                </>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="chat-message assistant">
            <div className="chat-message-role">AI</div>
            <div className="chat-message-content loading">Thinking...</div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {attachments.length > 0 && (
        <div className="attachments-preview">
          {attachments.map((att, i) => (
            <div key={i} className="attachment-chip">
              {att.type.startsWith('image/') ? (
                <img src={att.dataUrl} alt={att.name} className="attachment-thumb" />
              ) : (
                <span className="attachment-icon">{getFileExtLabel(att.name)}</span>
              )}
              <span className="attachment-name">{att.name}</span>
              <button
                className="attachment-remove"
                onClick={() => removeAttachment(i)}
                aria-label={`Remove ${att.name}`}
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="chat-input-area">
        <input
          ref={fileInputRef}
          type="file"
          className="file-input-hidden"
          accept="image/*,.pdf"
          multiple
          onChange={handleFileSelect}
        />
        <button
          className="attach-button"
          onClick={() => fileInputRef.current?.click()}
          disabled={loading}
          title="Attach file"
          aria-label="Attach file"
        >
          <svg width="18" height="18" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M15.621 4.379a3 3 0 00-4.242 0l-7 7a3 3 0 004.241 4.243h.001l.497-.5a.75.75 0 011.064 1.057l-.498.501a4.5 4.5 0 01-6.364-6.364l7-7a4.5 4.5 0 016.368 6.36l-3.455 3.553A2.625 2.625 0 119.52 9.52l3.45-3.451a.75.75 0 111.061 1.06l-3.45 3.451a1.125 1.125 0 001.587 1.595l3.454-3.553a3 3 0 000-4.242z"
              clipRule="evenodd"
            />
          </svg>
        </button>
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onCompositionStart={() => setIsComposing(true)}
          onCompositionEnd={() => setIsComposing(false)}
          placeholder="Type a message..."
          rows={1}
          disabled={loading}
        />
        <button
          onClick={sendMessage}
          disabled={loading || (!input.trim() && attachments.length === 0)}
        >
          Send
        </button>
      </div>
    </div>
  )
}

export default App
