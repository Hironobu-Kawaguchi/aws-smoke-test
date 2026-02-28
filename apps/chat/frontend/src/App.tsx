import { useEffect, useRef, useState } from 'react'
import './App.css'

async function sha256Hex(message: string): Promise<string> {
  const data = new TextEncoder().encode(message)
  const hashBuffer = await crypto.subtle.digest('SHA-256', data)
  const hashArray = Array.from(new Uint8Array(hashBuffer))
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('')
}

interface Message {
  role: 'user' | 'assistant'
  content: string
}

type AttachmentKind = 'image' | 'pdf'

interface Attachment {
  filename: string
  mime_type: string
  data_base64: string
  kind: AttachmentKind
}

const IMAGE_MIME_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/webp',
  'image/gif',
])

const PDF_MIME_TYPE = 'application/pdf'

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result
      if (typeof result !== 'string') {
        reject(new Error('ファイル読み込みに失敗しました'))
        return
      }
      const [, base64] = result.split(',')
      resolve(base64)
    }
    reader.onerror = () => reject(new Error('ファイル読み込みに失敗しました'))
    reader.readAsDataURL(file)
  })
}


function escapeHtml(input: string): string {
  return input
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function renderMarkdown(input: string): string {
  const escaped = escapeHtml(input)
  const withCodeBlocks = escaped.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
  const withInlineCode = withCodeBlocks.replace(/`([^`]+)`/g, '<code>$1</code>')
  const withBold = withInlineCode.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  const withItalic = withBold.replace(/(^|\W)\*([^*]+)\*(?=\W|$)/g, '$1<em>$2</em>')
  const withHeadings = withItalic
    .replace(/^### (.*)$/gm, '<h3>$1</h3>')
    .replace(/^## (.*)$/gm, '<h2>$1</h2>')
    .replace(/^# (.*)$/gm, '<h1>$1</h1>')
  const withLinks = withHeadings.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>')
  const withListItems = withLinks.replace(/^- (.*)$/gm, '<li>$1</li>')
  const withLists = withListItems.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>')
  return withLists.replace(/\n/g, '<br />')
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [model, setModel] = useState('gpt-4.1-mini')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [isComposing, setIsComposing] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const sendMessage = async () => {
    const text = input.trim()
    if ((!text && selectedFiles.length === 0) || loading) return

    const userLabel = selectedFiles.length > 0
      ? `${text}${text ? '\n\n' : ''}[添付: ${selectedFiles.map((f) => f.name).join(', ')}]`
      : text

    const userMessage: Message = { role: 'user', content: userLabel || '(添付ファイルのみ送信)' }
    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    setInput('')
    setLoading(true)

    try {
      const attachments: Attachment[] = []
      for (const file of selectedFiles) {
        const mimeType = file.type
        const kind: AttachmentKind | null = IMAGE_MIME_TYPES.has(mimeType)
          ? 'image'
          : mimeType === PDF_MIME_TYPE
            ? 'pdf'
            : null

        if (!kind) {
          throw new Error(`未対応のファイル形式です: ${file.name}`)
        }

        attachments.push({
          filename: file.name,
          mime_type: mimeType,
          data_base64: await fileToBase64(file),
          kind,
        })
      }

      const body = JSON.stringify({
        messages: updatedMessages,
        model,
        system_prompt: systemPrompt.trim() || null,
        attachments,
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
      setSelectedFiles([])
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

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // 日本語IME変換の確定Enterでは送信しない
    if (e.nativeEvent.isComposing || isComposing) {
      return
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? [])
    setSelectedFiles(files)
  }

  return (
    <div className="chat">
      <header className="chat-header">
        <h1>Chat</h1>
      </header>

      <div className="chat-settings">
        <label>
          Model
          <input value={model} onChange={(e) => setModel(e.target.value)} disabled={loading} />
        </label>
        <label>
          System Prompt
          <textarea
            value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            placeholder="Assistant behavior instructions"
            rows={2}
            disabled={loading}
          />
        </label>
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div className="chat-message-role">
              {msg.role === 'user' ? 'You' : 'AI'}
            </div>
            <div
              className="chat-message-content"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
            />
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
          onCompositionStart={() => setIsComposing(true)}
          onCompositionEnd={() => setIsComposing(false)}
          placeholder="Type a message..."
          rows={2}
          disabled={loading}
        />
        <div className="chat-input-actions">
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
          <button onClick={sendMessage} disabled={loading || (!input.trim() && selectedFiles.length === 0)}>
            Send
          </button>
        </div>
      </div>

      {selectedFiles.length > 0 && (
        <div className="selected-files">
          添付ファイル: {selectedFiles.map((f) => f.name).join(', ')}
        </div>
      )}
    </div>
  )
}

export default App
