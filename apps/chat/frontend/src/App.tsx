import { useState, useRef, useEffect, type ChangeEvent, type KeyboardEvent } from 'react'
import './App.css'

async function sha256Hex(message: string): Promise<string> {
  const data = new TextEncoder().encode(message)
  const hashBuffer = await crypto.subtle.digest('SHA-256', data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('')
}


function escapeHtml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
}

function renderMarkdown(markdown: string): string {
  const escaped = escapeHtml(markdown)
  return escaped
    .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/\[(.*?)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
    .replace(/\n/g, '<br/>')
}

interface Attachment {
  filename: string
  mimeType: string
  dataBase64: string
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  attachments?: Attachment[]
}

interface ChatOptions {
  model: string
  systemPrompt: string
  temperature?: number
}

const DEFAULT_OPTIONS: ChatOptions = {
  model: 'gpt-4.1-mini',
  systemPrompt: '',
  temperature: 0.7,
}

async function fileToAttachment(file: File): Promise<Attachment> {
  const arrayBuffer = await file.arrayBuffer()
  const bytes = new Uint8Array(arrayBuffer)
  let binary = ''
  for (const byte of bytes) {
    binary += String.fromCharCode(byte)
  }

  return {
    filename: file.name,
    mimeType: file.type || 'application/octet-stream',
    dataBase64: btoa(binary),
  }
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [options, setOptions] = useState<ChatOptions>(DEFAULT_OPTIONS)
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = async () => {
    const text = input.trim()
    if ((!text && attachments.length === 0) || loading) return

    const userMessage: Message = {
      role: 'user',
      content: text,
      attachments,
    }
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setInput('')
    setAttachments([])
    setLoading(true)

    try {
      const body = JSON.stringify({
        messages: updatedMessages,
        model: options.model,
        systemPrompt: options.systemPrompt,
        temperature: options.temperature,
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

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.nativeEvent.isComposing) {
      return
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const fileList = event.target.files
    if (!fileList || fileList.length === 0) return

    const allowedFiles = Array.from(fileList).filter(
      (file) => file.type.startsWith('image/') || file.type === 'application/pdf',
    )

    // 未対応ファイルは静かに除外し、対応形式だけを添付する。
    const nextAttachments = await Promise.all(allowedFiles.map(fileToAttachment))
    setAttachments(nextAttachments)
    event.target.value = ''
  }

  return (
    <div className="chat">
      <header className="chat-header">
        <h1>Chat</h1>
      </header>

      <section className="chat-options">
        <label>
          Model
          <input
            value={options.model}
            onChange={(e) => setOptions({ ...options, model: e.target.value })}
            disabled={loading}
          />
        </label>
        <label>
          Temperature
          <input
            type="number"
            min={0}
            max={2}
            step={0.1}
            value={options.temperature}
            onChange={(e) =>
              setOptions({ ...options, temperature: Number.parseFloat(e.target.value) })
            }
            disabled={loading}
          />
        </label>
        <label className="system-prompt-label">
          System prompt
          <textarea
            value={options.systemPrompt}
            onChange={(e) => setOptions({ ...options, systemPrompt: e.target.value })}
            rows={2}
            disabled={loading}
          />
        </label>
      </section>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div className="chat-message-role">{msg.role === 'user' ? 'You' : 'AI'}</div>
            <div className="chat-message-content markdown-content">
              <div dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
            </div>
            {msg.attachments && msg.attachments.length > 0 && (
              <ul className="attachment-list">
                {msg.attachments.map((attachment) => (
                  <li key={`${attachment.filename}-${attachment.dataBase64.length}`}>
                    📎 {attachment.filename}
                  </li>
                ))}
              </ul>
            )}
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

      <div className="chat-input-area">
        <textarea
          className="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          rows={1}
          disabled={loading}
        />
        <label className="file-input-label">
          添付
          <input
            type="file"
            accept="image/*,application/pdf"
            multiple
            onChange={handleFileChange}
            disabled={loading}
          />
        </label>
        <button onClick={sendMessage} disabled={loading || (!input.trim() && attachments.length === 0)}>
          Send
        </button>
      </div>
      {attachments.length > 0 && (
        <div className="selected-files">
          {attachments.map((attachment) => (
            <span key={`${attachment.filename}-${attachment.dataBase64.length}`}>📎 {attachment.filename}</span>
          ))}
        </div>
      )}
    </div>
  )
}

export default App
